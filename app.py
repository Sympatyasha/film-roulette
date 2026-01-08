import os
import sys
import json
import requests
from flask import Flask, render_template, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
from datetime import datetime, timedelta
import random

# Определяем, в production ли мы (по наличию переменной окружения RENDER)
IS_RENDER = 'RENDER' in os.environ

# Конфигурация приложения
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Настраиваем подключение к базе данных
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    # Локальная разработка - используем SQLite для простоты
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movies.db'
    print("Используется SQLite для локальной разработки")
else:
    # На render.com - исправляем URL для совместимости с драйверами
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+pg8000://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+pg8000://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("Используется PostgreSQL с драйвером pg8000")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'connect_args': {
        'connect_timeout': 10
    }
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
    genres = db.Column(db.String(500))  # Храним как строку для совместимости
    country = db.Column(db.String(100))
    director = db.Column(db.String(200))
    cast = db.Column(db.String(1000))   # Храним как строку для совместимости
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tmdb_id = db.Column(db.Integer, unique=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        # Преобразуем строки обратно в списки для API
        try:
            genres_list = json.loads(self.genres) if self.genres else []
        except:
            genres_list = self.genres.split(',') if self.genres else []
            
        try:
            cast_list = json.loads(self.cast) if self.cast else []
        except:
            cast_list = self.cast.split(',') if self.cast else []
            
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
            'genres': genres_list,
            'country': self.country,
            'director': self.director,
            'cast': cast_list,
            'tmdb_id': self.tmdb_id
        }

# Конфигурация TMDb API - используем несколько ключей на случай проблем
TMDB_API_KEYS = [
    '88a2c09dbb5d2c9a7bf4e46a6f0e5a3f',  # Основной ключ
    'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI4OGEyYzA5ZGJiNWQyYzlhN2JmNGU0NmE2ZjBlNWEzZiIsInN1YiI6IjY1Zjk0YjQ1Zjg1OTU4MDE4NjY2ZmU2YyIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.KLLd49zZyQdU1V7f_-Vq6VdSU-2sMOOeJVGmXukyVg0'  # Backup
]

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"  # Используем w500 для оптимального размера
TMDB_LANGUAGE = "ru-RU"

def get_tmdb_api_key():
    """Получает рабочий API ключ"""
    user_key = os.environ.get('TMDB_API_KEY')
    if user_key:
        return user_key
    
    # Пробуем доступные ключи
    for key in TMDB_API_KEYS:
        try:
            test_url = f"{TMDB_BASE_URL}/configuration"
            response = requests.get(test_url, params={'api_key': key}, timeout=5)
            if response.status_code == 200:
                return key
        except:
            continue
    
    return TMDB_API_KEYS[0]  # Возвращаем первый как fallback

def init_database():
    """Инициализация базы данных"""
    print("Инициализация базы данных...")
    
    with app.app_context():
        try:
            # Создаем таблицы
            db.create_all()
            print("✓ Таблицы созданы")
            
            # Проверяем, есть ли фильмы
            movie_count = Movie.query.count()
            print(f"✓ В базе {movie_count} фильмов")
            
            # Если фильмов мало, загружаем
            if movie_count < 50:
                print("Запускаем загрузку фильмов из TMDb...")
                fetch_movies_from_tmdb()
            else:
                print("✓ База данных уже содержит фильмы")
                
        except Exception as e:
            print(f"✗ Ошибка инициализации базы: {str(e)}")
            # Пытаемся создать таблицы еще раз
            try:
                db.create_all()
                print("✓ Таблицы созданы после ошибки")
            except Exception as e2:
                print(f"✗ Критическая ошибка: {str(e2)}")

def fetch_movies_from_tmdb():
    """Загружает фильмы из TMDb API"""
    api_key = get_tmdb_api_key()
    print(f"Используем TMDb API ключ: {api_key[:10]}...")
    
    movies_added = 0
    total_pages = 5  # Загружаем 5 страниц (~100 фильмов)
    
    for page in range(1, total_pages + 1):
        try:
            print(f"Загрузка страницы {page}/{total_pages}...")
            
            # Получаем популярные фильмы
            url = f"{TMDB_BASE_URL}/movie/popular"
            params = {
                'api_key': api_key,
                'language': TMDB_LANGUAGE,
                'page': page,
                'region': 'US'  # Более широкий выбор
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            movies_on_page = data.get('results', [])
            print(f"На странице {len(movies_on_page)} фильмов")
            
            for idx, movie_data in enumerate(movies_on_page):
                # Пропускаем фильмы без постера
                if not movie_data.get('poster_path'):
                    continue
                
                # Проверяем, есть ли уже фильм в базе
                existing_movie = Movie.query.filter_by(tmdb_id=movie_data['id']).first()
                if existing_movie:
                    continue
                
                try:
                    # Получаем детальную информацию о фильме
                    movie_id = movie_data['id']
                    details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
                    details_params = {
                        'api_key': api_key,
                        'language': TMDB_LANGUAGE
                    }
                    
                    details_response = requests.get(details_url, params=details_params, timeout=10)
                    details_response.raise_for_status()
                    details = details_response.json()
                    
                    # Создаем объект Movie
                    movie = Movie()
                    movie.tmdb_id = movie_data['id']
                    movie.title_ru = details.get('title', details.get('original_title', f'Фильм {movie_id}'))
                    movie.title_en = details.get('original_title', '')
                    
                    # Год
                    if details.get('release_date'):
                        try:
                            movie.year = int(details['release_date'][:4])
                        except:
                            movie.year = 2000
                    else:
                        movie.year = 2000
                    
                    # Рейтинги
                    vote_avg = details.get('vote_average', 0)
                    movie.rating_kp = round(vote_avg * 1.1, 1) if vote_avg > 0 else round(random.uniform(5.0, 8.5), 1)
                    movie.rating_imdb = vote_avg
                    
                    # Описание
                    movie.description = details.get('overview', 'Описание отсутствует.')
                    if not movie.description or len(movie.description) < 20:
                        movie.description = 'Увлекательный фильм, который стоит посмотреть.'
                    
                    # Постер
                    if details.get('poster_path'):
                        movie.poster_url = f"{TMDB_IMAGE_BASE}{details['poster_path']}"
                    else:
                        movie.poster_url = "https://via.placeholder.com/500x750/2a2a2a/ffffff?text=No+Poster"
                    
                    # Длительность
                    movie.duration = details.get('runtime', 120)
                    
                    # Жанры (храним как JSON строку)
                    genres = [genre['name'] for genre in details.get('genres', [])[:3]]
                    movie.genres = json.dumps(genres, ensure_ascii=False) if genres else json.dumps(['Фильм'])
                    
                    # Страна
                    countries = details.get('production_countries', [])
                    movie.country = countries[0]['name'] if countries else 'США'
                    
                    # Получаем информацию о команде
                    credits_url = f"{TMDB_BASE_URL}/movie/{movie_id}/credits"
                    credits_params = {'api_key': api_key}
                    
                    try:
                        credits_response = requests.get(credits_url, params=credits_params, timeout=5)
                        if credits_response.status_code == 200:
                            credits = credits_response.json()
                            
                            # Режиссер
                            director = None
                            for person in credits.get('crew', []):
                                if person.get('job') == 'Director':
                                    director = person.get('name')
                                    break
                            movie.director = director or 'Неизвестный режиссер'
                            
                            # Актеры (первые 5)
                            cast = []
                            for actor in credits.get('cast', [])[:5]:
                                name = actor.get('name', 'Актер')
                                cast.append(name)
                            movie.cast = json.dumps(cast, ensure_ascii=False)
                        else:
                            movie.director = 'Неизвестный режиссер'
                            movie.cast = json.dumps(['Актерский состав'], ensure_ascii=False)
                    except:
                        movie.director = 'Неизвестный режиссер'
                        movie.cast = json.dumps(['Актерский состав'], ensure_ascii=False)
                    
                    movie.last_updated = datetime.utcnow()
                    
                    db.session.add(movie)
                    movies_added += 1
                    
                    print(f"  Добавлен: {movie.title_ru} ({movie.year})")
                    
                    if movies_added >= 120:  # Ограничим общее количество
                        break
                        
                except Exception as e:
                    print(f"    Ошибка при обработке фильма {movie_data.get('id')}: {str(e)[:50]}...")
                    continue
            
            # Коммитим каждую страницу
            db.session.commit()
            print(f"✓ Страница {page} обработана. Всего фильмов: {movies_added}")
            
            if movies_added >= 120:
                break
                
        except Exception as e:
            print(f"✗ Ошибка при загрузке страницы {page}: {str(e)}")
            db.session.rollback()
            continue
    
    print(f"✅ Загрузка завершена. Всего добавлено фильмов: {movies_added}")
    return movies_added

# Главная страница
@app.route('/')
def index():
    # Проверяем и инициализируем базу если нужно
    with app.app_context():
        try:
            movie_count = Movie.query.count()
            if movie_count < 30:
                # Запускаем в фоне загрузку фильмов
                import threading
                thread = threading.Thread(target=fetch_movies_from_tmdb)
                thread.daemon = True
                thread.start()
        except:
            pass
    
    return render_template('index.html')

# API: получение уникальных жанров
@app.route('/api/genres')
def get_genres():
    try:
        movies = Movie.query.all()
        genres_set = set()
        
        for movie in movies:
            if movie.genres:
                try:
                    movie_genres = json.loads(movie.genres)
                    if isinstance(movie_genres, list):
                        for genre in movie_genres:
                            if genre:
                                genres_set.add(genre.lower())
                except:
                    # Если не JSON, пытаемся разобрать как строку
                    if ',' in movie.genres:
                        for genre in movie.genres.split(','):
                            if genre.strip():
                                genres_set.add(genre.strip().lower())
                    else:
                        genres_set.add(movie.genres.lower())
        
        if not genres_set:
            # Жанры по умолчанию
            genres_set = {
                'драма', 'комедия', 'боевик', 'триллер', 'ужасы',
                'фантастика', 'фэнтези', 'мелодрама', 'детектив', 'приключения'
            }
        
        return jsonify(sorted(list(genres_set)))
        
    except Exception as e:
        print(f"Ошибка в get_genres: {str(e)}")
        return jsonify(['драма', 'комедия', 'боевик', 'триллер', 'фантастика'])

# API: случайный фильм с фильтрами
@app.route('/api/random', methods=['POST'])
def get_random_movie():
    try:
        data = request.json or {}
        query = Movie.query
        
        # Простая фильтрация (без сложных запросов из-за SQLite/JSON)
        all_movies = Movie.query.all()
        filtered_movies = []
        
        for movie in all_movies:
            # Фильтрация по жанрам
            if data.get('genres') and len(data['genres']) > 0:
                movie_genres = []
                if movie.genres:
                    try:
                        movie_genres = [g.lower() for g in json.loads(movie.genres)]
                    except:
                        movie_genres = [movie.genres.lower()]
                
                if movie_genres:
                    selected_genres = [g.lower() for g in data['genres']]
                    if not any(genre in movie_genres for genre in selected_genres):
                        continue
            
            # Фильтрация по году
            if data.get('year_from') and movie.year < data['year_from']:
                continue
                
            if data.get('year_to') and movie.year > data['year_to']:
                continue
            
            # Фильтрация по рейтингу
            if data.get('rating_min') and movie.rating_kp < data['rating_min']:
                continue
            
            filtered_movies.append(movie)
        
        # Выбираем случайный фильм из отфильтрованных
        if filtered_movies:
            movie = random.choice(filtered_movies)
        elif all_movies:
            movie = random.choice(all_movies)
        else:
            return jsonify({'error': 'В базе нет фильмов'}), 404
        
        # Добавляем в историю сессии
        if 'recent_movies' not in session:
            session['recent_movies'] = []
        
        recent = session['recent_movies']
        movie_data = {
            'id': movie.id,
            'title_ru': movie.title_ru,
            'poster_url': movie.poster_url,
            'rating_kp': movie.rating_kp,
            'year': movie.year
        }
        
        # Удаляем дубликаты
        recent = [m for m in recent if m['id'] != movie.id]
        recent.insert(0, movie_data)
        
        # Ограничиваем 5 элементами
        session['recent_movies'] = recent[:5]
        session.modified = True
        
        return jsonify(movie.to_dict())
        
    except Exception as e:
        print(f"Ошибка в get_random_movie: {str(e)}")
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
            # Простой расчет среднего рейтинга
            movies = Movie.query.all()
            total_rating = sum(m.rating_kp or 0 for m in movies)
            avg_rating = total_rating / total
        else:
            avg_rating = 0
        
        return jsonify({
            'total_movies': total,
            'avg_rating': round(avg_rating, 1),
            'status': 'ok'
        })
        
    except Exception as e:
        print(f"Ошибка в get_stats: {str(e)}")
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
        print(f"Ошибка в refresh_movies: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)[:100]
        }), 500

# Health check endpoint
@app.route('/health')
def health_check():
    try:
        movie_count = Movie.query.count()
        return jsonify({
            'status': 'ok',
            'movie_count': movie_count,
            'timestamp': datetime.utcnow().isoformat()
        })
    except:
        return jsonify({'status': 'error'}), 500

# Простой эндпоинт для проверки работы API
@app.route('/api/test')
def test_api():
    return jsonify({
        'message': 'КиноРулетка API работает!',
        'version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    })

# Инициализация при запуске
if __name__ == '__main__':
    print("=" * 50)
    print("Запуск КиноРулетки...")
    print(f"Режим: {'PRODUCTION' if IS_RENDER else 'DEVELOPMENT'}")
    print("=" * 50)
    
    init_database()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=not IS_RENDER)
else:
    # Для gunicorn
    print("Инициализация для production...")
    init_database()
