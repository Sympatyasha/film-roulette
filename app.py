import os
import json
import requests
from flask import Flask, render_template, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
from datetime import datetime, timedelta
import random
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Исправление URL для PostgreSQL на render.com
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Решаем проблему с psycopg2 и render.com
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

db = SQLAlchemy(app)

# Модель Movie
class Movie(db.Model):
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    title_ru = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200))
    year = db.Column(db.Integer, nullable=False)
    rating_kp = db.Column(db.Float)
    rating_imdb = db.Column(db.Float)
    description = db.Column(db.Text)
    poster_url = db.Column(db.String(500))
    duration = db.Column(db.Integer)
    genres = db.Column(db.JSON)
    country = db.Column(db.String(100))
    director = db.Column(db.String(200))
    cast = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tmdb_id = db.Column(db.Integer, unique=True)
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

def init_database():
    """Инициализация базы данных"""
    with app.app_context():
        try:
            db.create_all()
            print("Таблицы созданы успешно")
            
            # Проверяем, есть ли фильмы
            movie_count = Movie.query.count()
            print(f"В базе {movie_count} фильмов")
            
            # Если фильмов мало, загружаем
            if movie_count < 50:
                print("Запускаем загрузку фильмов...")
                fetch_movies_from_tmdb()
                
        except Exception as e:
            print(f"Ошибка инициализации базы: {str(e)}")
            # Создаем таблицы если их нет
            try:
                db.create_all()
            except:
                pass

def fetch_movies_from_tmdb():
    """Загружает фильмы из TMDb API"""
    print("Загрузка фильмов из TMDb...")
    
    movies_added = 0
    total_pages = 5  # Уменьшим количество страниц для скорости
    
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
                # Пропускаем фильмы без постера
                if not movie_data.get('poster_path'):
                    continue
                
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
                
                # Год
                if details.get('release_date'):
                    try:
                        movie.year = int(details['release_date'].split('-')[0])
                    except:
                        movie.year = 2000
                else:
                    movie.year = 2000
                
                # Рейтинги
                vote_avg = details.get('vote_average', 0)
                movie.rating_kp = round(vote_avg * 1.1, 1) if vote_avg > 0 else round(random.uniform(6.0, 8.5), 1)
                movie.rating_imdb = vote_avg
                
                # Описание
                movie.description = details.get('overview', 'Описание отсутствует')
                if not movie.description:
                    movie.description = 'Описание фильма пока не добавлено.'
                
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
                
                if movies_added >= 100:  # Максимум 100 фильмов для первого раза
                    break
            
            if movies_added >= 100:
                break
                
            print(f"Загружено {movies_added} фильмов...")
            
        except Exception as e:
            print(f"Ошибка при загрузке страницы {page}: {str(e)}")
            continue
    
    try:
        db.session.commit()
        print(f"Успешно добавлено {movies_added} фильмов в базу данных")
        return movies_added
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при сохранении фильмов: {str(e)}")
        return 0

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# API: получение уникальных жанров
@app.route('/api/genres')
def get_genres():
    try:
        movies = Movie.query.all()
        genres_set = set()
        for movie in movies:
            if movie.genres:
                for genre in movie.genres:
                    genres_set.add(genre.lower())
        return jsonify(sorted(list(genres_set)))
    except Exception as e:
        # Возвращаем жанры по умолчанию если база не готова
        return jsonify(['драма', 'комедия', 'боевик', 'триллер', 'ужасы', 'фантастика'])

# API: случайный фильм с фильтрами
@app.route('/api/random', methods=['POST'])
def get_random_movie():
    try:
        data = request.json
        query = Movie.query
        
        # Применяем фильтры
        if data.get('genres') and len(data['genres']) > 0:
            selected_genres = [g.lower() for g in data['genres']]
            # Простая фильтрация по жанрам
            movies = Movie.query.all()
            filtered_movies = []
            for movie in movies:
                if movie.genres:
                    movie_genres = [g.lower() for g in movie.genres]
                    if any(genre in movie_genres for genre in selected_genres):
                        filtered_movies.append(movie)
            
            if filtered_movies:
                movie = random.choice(filtered_movies)
            else:
                movie = Movie.query.order_by(func.random()).first()
        else:
            # Без фильтрации по жанрам
            if data.get('year_from'):
                query = query.filter(Movie.year >= data['year_from'])
            if data.get('year_to'):
                query = query.filter(Movie.year <= data['year_to'])
            
            if data.get('rating_min'):
                query = query.filter(Movie.rating_kp >= data['rating_min'])
            
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
        
    except Exception as e:
        print(f"Ошибка в /api/random: {str(e)}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

# API: последние просмотренные
@app.route('/api/recent')
def get_recent():
    recent = session.get('recent_movies', [])
    return jsonify(recent)

# API: статистика
@app.route('/api/stats')
def get_stats():
    try:
        total = Movie.query.count()
        if total > 0:
            avg_rating = db.session.query(db.func.avg(Movie.rating_kp)).scalar() or 0
        else:
            avg_rating = 0
            
        return jsonify({
            'total_movies': total,
            'avg_rating': round(float(avg_rating), 1),
            'status': 'ok'
        })
    except Exception as e:
        print(f"Ошибка в /api/stats: {str(e)}")
        return jsonify({
            'total_movies': 0,
            'avg_rating': 0,
            'status': 'error'
        })

# API: принудительное обновление фильмов
@app.route('/api/refresh', methods=['POST'])
def refresh_movies():
    try:
        count = fetch_movies_from_tmdb()
        return jsonify({
            'status': 'success',
            'message': f'Добавлено {count} новых фильмов',
            'total': Movie.query.count()
        })
    except Exception as e:
        print(f"Ошибка в /api/refresh: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Health check endpoint для render.com
@app.route('/health')
def health_check():
    return jsonify({'status': 'ok', 'message': 'Сервер работает'})

# Инициализация при запуске
if __name__ == '__main__':
    print("Запуск инициализации базы данных...")
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Для gunicorn
    print("Инициализация базы данных для production...")
    init_database()
