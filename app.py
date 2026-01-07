import os
import json
import requests
from flask import Flask, render_template, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Модель Movie
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title_ru = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200))
    year = db.Column(db.Integer, nullable=False)
    rating_kp = db.Column(db.Float)
    rating_imdb = db.Column(db.Float)
    description = db.Column(db.Text)
    poster_url = db.Column(db.String(500))
    duration = db.Column(db.Integer)  # в минутах
    genres = db.Column(db.JSON)  # список жанров ['драма', 'комедия']
    country = db.Column(db.String(100))
    director = db.Column(db.String(200))
    cast = db.Column(db.JSON)  # список актеров
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tmdb_id = db.Column(db.Integer, unique=True)  # ID из TMDb
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title_ru': self.title_ru,
            'title_en': self.title_en,
            'year': self.year,
            'rating_kp': self.rating_kp,
            'rating_imdb': self.rating_imdb,
            'description': self.description,
            'poster_url': self.poster_url,
            'duration': self.duration,
            'genres': self.genres,
            'country': self.country,
            'director': self.director,
            'cast': self.cast,
            'tmdb_id': self.tmdb_id
        }

# Конфигурация TMDb API
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '88a2c09dbb5d2c9a7bf4e46a6f0e5a3f')
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TMDB_LANGUAGE = "ru-RU"

def fetch_movies_from_tmdb():
    """Загружает фильмы из TMDb API"""
    print("Загрузка фильмов из TMDb...")
    
    movies_added = 0
    total_pages = 10  # Загрузим 10 страниц (до 200 фильмов)
    
    for page in range(1, total_pages + 1):
        try:
            # Получаем популярные фильмы
            url = f"{TMDB_BASE_URL}/movie/popular"
            params = {
                'api_key': TMDB_API_KEY,
                'language': TMDB_LANGUAGE,
                'page': page,
                'region': 'RU'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for movie_data in data['results']:
                # Проверяем, есть ли уже фильм в базе
                existing_movie = Movie.query.filter_by(tmdb_id=movie_data['id']).first()
                if existing_movie:
                    continue
                
                # Получаем детальную информацию о фильме
                movie_id = movie_data['id']
                details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
                details_params = {
                    'api_key': TMDB_API_KEY,
                    'language': TMDB_LANGUAGE,
                    'append_to_response': 'credits'
                }
                
                details_response = requests.get(details_url, params=details_params, timeout=10)
                details_response.raise_for_status()
                details = details_response.json()
                
                # Преобразуем данные TMDb в нашу модель
                movie = Movie()
                movie.tmdb_id = movie_data['id']
                movie.title_ru = details.get('title', details.get('original_title', 'Без названия'))
                movie.title_en = details.get('original_title', '')
                movie.year = int(details.get('release_date', '2000').split('-')[0]) if details.get('release_date') else 2000
                movie.rating_kp = round(details.get('vote_average', 0) * 1.1, 1)  # Конвертируем в шкалу КиноПоиска
                movie.rating_imdb = details.get('vote_average', 0)
                movie.description = details.get('overview', 'Описание отсутствует')
                
                # Постер
                if details.get('poster_path'):
                    movie.poster_url = f"{TMDB_IMAGE_BASE}{details['poster_path']}"
                else:
                    movie.poster_url = "https://via.placeholder.com/300x450?text=No+Poster"
                
                # Длительность
                movie.duration = details.get('runtime', 0)
                
                # Жанры
                genres = [genre['name'] for genre in details.get('genres', [])[:3]]
                movie.genres = genres if genres else ['драма']
                
                # Страна
                countries = details.get('production_countries', [])
                movie.country = countries[0]['name'] if countries else 'США'
                
                # Режиссер
                director = None
                for person in details.get('credits', {}).get('crew', []):
                    if person.get('job') == 'Director':
                        director = person.get('name')
                        break
                movie.director = director or 'Неизвестно'
                
                # Актеры (первые 5)
                cast = []
                for actor in details.get('credits', {}).get('cast', [])[:5]:
                    cast.append(actor.get('name', 'Неизвестно'))
                movie.cast = cast
                
                movie.last_updated = datetime.utcnow()
                
                db.session.add(movie)
                movies_added += 1
                
                if movies_added >= 200:  # Максимум 200 фильмов
                    break
            
            if movies_added >= 200:
                break
                
            print(f"Загружено {movies_added} фильмов...")
            
        except Exception as e:
            print(f"Ошибка при загрузке страницы {page}: {str(e)}")
            continue
    
    try:
        db.session.commit()
        print(f"Успешно добавлено {movies_added} фильмов в базу данных")
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при сохранении фильмов: {str(e)}")
    
    return movies_added

def update_old_movies():
    """Обновляет старые записи фильмов"""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    old_movies = Movie.query.filter(Movie.last_updated < thirty_days_ago).limit(20).all()
    
    for movie in old_movies:
        try:
            # Обновляем данные фильма
            url = f"{TMDB_BASE_URL}/movie/{movie.tmdb_id}"
            params = {
                'api_key': TMDB_API_KEY,
                'language': TMDB_LANGUAGE
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                movie.rating_kp = round(data.get('vote_average', 0) * 1.1, 1)
                movie.rating_imdb = data.get('vote_average', 0)
                movie.last_updated = datetime.utcnow()
        
        except Exception as e:
            print(f"Ошибка при обновлении фильма {movie.id}: {str(e)}")
            continue
    
    try:
        db.session.commit()
        print(f"Обновлено {len(old_movies)} фильмов")
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при обновлении фильмов: {str(e)}")

# Главная страница
@app.route('/')
def index():
    # Проверяем, есть ли фильмы в базе
    movie_count = Movie.query.count()
    if movie_count < 50:
        # Автоматически загружаем фильмы если их мало
        fetch_movies_from_tmdb()
    
    # Обновляем старые записи (раз в день)
    update_old_movies()
    
    return render_template('index.html')

# API: получение уникальных жанров
@app.route('/api/genres')
def get_genres():
    movies = Movie.query.all()
    genres_set = set()
    for movie in movies:
        if movie.genres:
            for genre in movie.genres:
                genres_set.add(genre.lower())
    return jsonify(sorted(list(genres_set)))

# API: случайный фильм с фильтрами
@app.route('/api/random', methods=['POST'])
def get_random_movie():
    data = request.json
    query = Movie.query
    
    # Применяем фильтры
    if data.get('genres') and len(data['genres']) > 0:
        # Фильтрация по жанрам
        selected_genres = [g.lower() for g in data['genres']]
        genre_conditions = []
        for genre in selected_genres:
            # Ищем жанры в JSON поле
            genre_conditions.append(Movie.genres.cast(db.String).ilike(f'%{genre}%'))
        if genre_conditions:
            query = query.filter(db.or_(*genre_conditions))
    
    if data.get('year_from'):
        query = query.filter(Movie.year >= data['year_from'])
    if data.get('year_to'):
        query = query.filter(Movie.year <= data['year_to'])
    
    if data.get('rating_min'):
        query = query.filter(Movie.rating_kp >= data['rating_min'])
    
    # Случайный фильм
    movie = query.order_by(func.random()).first()
    
    if movie:
        # Добавляем в историю сессии
        if 'recent_movies' not in session:
            session['recent_movies'] = []
        
        recent = session['recent_movies']
        movie_data = {
            'id': movie.id,
            'title_ru': movie.title_ru,
            'poster_url': movie.poster_url,
            'rating_kp': movie.rating_kp,
            'year': movie.year,
            'tmdb_id': movie.tmdb_id
        }
        
        # Удаляем дубликаты
        recent = [m for m in recent if m['id'] != movie.id]
        recent.insert(0, movie_data)
        
        # Ограничиваем 5 элементами
        session['recent_movies'] = recent[:5]
        session.modified = True
        
        return jsonify(movie.to_dict())
    
    return jsonify({'error': 'Фильмы не найдены по заданным критериям'}), 404

# API: последние просмотренные
@app.route('/api/recent')
def get_recent():
    recent = session.get('recent_movies', [])
    return jsonify(recent)

# API: статистика
@app.route('/api/stats')
def get_stats():
    total = Movie.query.count()
    avg_rating = db.session.query(db.func.avg(Movie.rating_kp)).scalar() or 0
    recent_added = Movie.query.order_by(Movie.created_at.desc()).limit(5).all()
    
    return jsonify({
        'total_movies': total,
        'avg_rating': round(float(avg_rating), 1),
        'recent_added': [m.to_dict() for m in recent_added]
    })

# API: принудительное обновление фильмов
@app.route('/api/refresh', methods=['POST'])
def refresh_movies():
    count = fetch_movies_from_tmdb()
    return jsonify({
        'status': 'success',
        'message': f'Добавлено {count} новых фильмов',
        'total': Movie.query.count()
    })

# Инициализация базы данных
@app.before_first_request
def initialize_database():
    try:
        db.create_all()
        # Если база пуста, загружаем фильмы
        if Movie.query.count() < 50:
            fetch_movies_from_tmdb()
    except Exception as e:
        print(f"Ошибка инициализации базы: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)
