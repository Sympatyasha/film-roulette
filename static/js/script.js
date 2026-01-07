document.addEventListener('DOMContentLoaded', function() {
    // Элементы
    const spinButton = document.getElementById('spinButton');
    const filtersToggle = document.getElementById('filtersToggle');
    const filtersPanel = document.getElementById('filtersPanel');
    const genreChips = document.getElementById('genreChips');
    const yearFrom = document.getElementById('yearFrom');
    const yearTo = document.getElementById('yearTo');
    const ratingSlider = document.getElementById('ratingSlider');
    const ratingValue = document.getElementById('ratingValue');
    const resetFilters = document.getElementById('resetFilters');
    const resultSection = document.getElementById('resultSection');
    const historyList = document.getElementById('historyList');
    const movieCount = document.getElementById('movieCount');
    const avgRating = document.getElementById('avgRating');
    const lastUpdate = document.getElementById('lastUpdate');
    
    // Состояние
    let selectedGenres = [];
    let genres = [];
    
    // Инициализация
    initApp();
    
    // Инициализация приложения
    async function initApp() {
        await loadGenres();
        loadHistory();
        loadStats();
        updateRatingValue();
        
        // Загружаем историю при загрузке страницы
        setTimeout(loadHistory, 1000);
        
        // Показываем уведомление при первом посещении
        showWelcomeNotification();
    }
    
    // Обработчики событий
    filtersToggle.addEventListener('click', function() {
        filtersPanel.classList.toggle('active');
    });
    
    ratingSlider.addEventListener('input', updateRatingValue);
    
    resetFilters.addEventListener('click', function() {
        selectedGenres = [];
        yearFrom.value = '';
        yearTo.value = '';
        ratingSlider.value = '5.0';
        updateRatingValue();
        updateGenreChips();
    });
    
    spinButton.addEventListener('click', spinRoulette);
    
    // Добавляем кнопку обновления в DOM
    const refreshBtn = document.createElement('div');
    refreshBtn.className = 'refresh-btn';
    refreshBtn.innerHTML = `
        <i class="fas fa-sync-alt"></i>
        <div class="tooltip">Обновить фильмы</div>
    `;
    refreshBtn.addEventListener('click', refreshMovies);
    document.body.appendChild(refreshBtn);
    
    // Функции
    function updateRatingValue() {
        const value = parseFloat(ratingSlider.value).toFixed(1);
        ratingValue.textContent = `${value}+`;
    }
    
    async function loadGenres() {
        try {
            const response = await fetch('/api/genres');
            genres = await response.json();
            renderGenreChips();
        } catch (error) {
            console.error('Ошибка загрузки жанров:', error);
            // Используем жанры по умолчанию
            genres = [
                'драма', 'комедия', 'боевик', 'триллер', 'ужасы',
                'фантастика', 'фэнтези', 'мелодрама', 'детектив', 'приключения',
                'криминал', 'биография', 'история', 'мультфильм', 'семейный',
                'вестерн', 'военный', 'мюзикл', 'спорт', 'документальный'
            ];
            renderGenreChips();
        }
    }
    
    function renderGenreChips() {
        genreChips.innerHTML = '';
        genres.forEach(genre => {
            const chip = document.createElement('span');
            chip.className = 'genre-chip';
            chip.textContent = genre;
            chip.dataset.genre = genre.toLowerCase();
            
            chip.addEventListener('click', function() {
                const genre = this.dataset.genre;
                const index = selectedGenres.indexOf(genre);
                
                if (index === -1) {
                    selectedGenres.push(genre);
                } else {
                    selectedGenres.splice(index, 1);
                }
                
                updateGenreChips();
            });
            
            genreChips.appendChild(chip);
        });
        updateGenreChips();
    }
    
    function updateGenreChips() {
        document.querySelectorAll('.genre-chip').forEach(chip => {
            if (selectedGenres.includes(chip.dataset.genre)) {
                chip.classList.add('selected');
            } else {
                chip.classList.remove('selected');
            }
        });
    }
    
    async function spinRoulette() {
        // Блокируем кнопку
        spinButton.disabled = true;
        spinButton.innerHTML = `
            <div class="spin-button-inner">
                <span class="spin-text">КРУТИМ...</span>
                <div class="spinner"></div>
            </div>
        `;
        
        // Показываем скелетон
        showSkeleton();
        
        // Собираем фильтры
        const filters = {
            genres: selectedGenres,
            year_from: yearFrom.value ? parseInt(yearFrom.value) : null,
            year_to: yearTo.value ? parseInt(yearTo.value) : null,
            rating_min: parseFloat(ratingSlider.value)
        };
        
        try {
            const response = await fetch('/api/random', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(filters)
            });
            
            if (!response.ok) {
                throw new Error('Фильм не найден');
            }
            
            const movie = await response.json();
            displayMovie(movie);
            loadHistory();
            
        } catch (error) {
            resultSection.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Фильмы не найдены</h3>
                    <p>Попробуйте изменить критерии поиска</p>
                    <p style="margin-top: 15px; font-size: 14px;">
                        <a href="#" onclick="refreshMovies(); return false;">Обновить базу фильмов</a>
                    </p>
                </div>
            `;
        } finally {
            // Восстанавливаем кнопку
            spinButton.disabled = false;
            spinButton.innerHTML = `
                <div class="spin-button-inner">
                    <span class="spin-text">КРУТИТЬ РУЛЕТКУ!</span>
                    <div class="film-reel">
                        <div class="film-hole"></div>
                        <div class="film-hole"></div>
                        <div class="film-hole"></div>
                        <div class="film-hole"></div>
                    </div>
                </div>
            `;
        }
    }
    
    function showSkeleton() {
        const template = document.getElementById('skeletonTemplate');
        const clone = template.content.cloneNode(true);
        resultSection.innerHTML = '';
        resultSection.appendChild(clone);
    }
    
    function displayMovie(movie) {
        const template = document.getElementById('movieCardTemplate');
        const clone = template.content.cloneNode(true);
        
        // Заполняем данные
        const posterImg = clone.querySelector('.poster-image');
        posterImg.src = movie.poster_url || 'https://via.placeholder.com/300x450?text=No+Poster';
        posterImg.alt = movie.title_ru;
        
        // Рейтинг
        const ratingEl = clone.querySelector('.movie-rating');
        const rating = movie.rating_kp || 0;
        ratingEl.textContent = rating.toFixed(1);
        
        if (rating >= 7) ratingEl.classList.add('rating-high');
        else if (rating >= 5) ratingEl.classList.add('rating-medium');
        else ratingEl.classList.add('rating-low');
        
        // Основная информация
        clone.querySelector('.movie-title').textContent = movie.title_ru;
        clone.querySelector('.movie-year').textContent = movie.year || '?';
        
        if (movie.duration) {
            const hours = Math.floor(movie.duration / 60);
            const minutes = movie.duration % 60;
            clone.querySelector('.movie-duration').textContent = 
                hours > 0 ? `${hours}ч ${minutes}м` : `${minutes}м`;
        } else {
            clone.querySelector('.movie-duration').textContent = '';
        }
        
        clone.querySelector('.movie-country').textContent = movie.country || '';
        
        // Жанры
        const genresContainer = clone.querySelector('.movie-genres');
        if (movie.genres && Array.isArray(movie.genres)) {
            movie.genres.forEach(genre => {
                const tag = document.createElement('span');
                tag.className = 'genre-tag';
                tag.textContent = genre;
                genresContainer.appendChild(tag);
            });
        }
        
        // Описание
        clone.querySelector('.movie-description').textContent = 
            movie.description || 'Описание отсутствует';
        
        // Режиссер и актеры
        clone.querySelector('.director-name').textContent = movie.director || 'Неизвестно';
        
        const castList = movie.cast && Array.isArray(movie.cast) 
            ? movie.cast.slice(0, 5).join(', ')
            : 'Неизвестно';
        clone.querySelector('.cast-list').textContent = castList;
        
        // Рейтинги
        clone.querySelector('.rating-kp').textContent = movie.rating_kp ? movie.rating_kp.toFixed(1) : '—';
        clone.querySelector('.rating-imdb').textContent = movie.rating_imdb ? movie.rating_imdb.toFixed(1) : '—';
        
        // Добавляем ссылку на TMDb если есть ID
        if (movie.tmdb_id) {
            const infoDiv = clone.querySelector('.movie-info');
            const tmdbLink = document.createElement('a');
            tmdbLink.href = `https://www.themoviedb.org/movie/${movie.tmdb_id}`;
            tmdbLink.target = '_blank';
            tmdbLink.className = 'tmdb-link';
            tmdbLink.innerHTML = '<i class="fab fa-imdb"></i> Подробнее на TMDb';
            infoDiv.appendChild(tmdbLink);
        }
        
        resultSection.innerHTML = '';
        resultSection.appendChild(clone);
    }
    
    async function loadHistory() {
        try {
            const response = await fetch('/api/recent');
            const history = await response.json();
            renderHistory(history);
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
        }
    }
    
    function renderHistory(history) {
        historyList.innerHTML = '';
        
        if (history.length === 0) {
            historyList.innerHTML = '<p class="no-history">История пуста</p>';
            return;
        }
        
        const template = document.getElementById('historyCardTemplate');
        
        history.forEach(movie => {
            const clone = template.content.cloneNode(true);
            
            clone.querySelector('.history-poster-image').src = 
                movie.poster_url || 'https://via.placeholder.com/150x200?text=No+Poster';
            clone.querySelector('.history-poster-image').alt = movie.title_ru;
            clone.querySelector('.history-rating').textContent = 
                movie.rating_kp ? movie.rating_kp.toFixed(1) : '?';
            clone.querySelector('.history-title').textContent = movie.title_ru;
            
            // При клике на карточку истории показываем фильм
            const card = clone.querySelector('.history-card');
            card.addEventListener('click', async () => {
                try {
                    const response = await fetch('/api/random', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ genres: [], year_from: null, year_to: null, rating_min: 0 })
                    });
                    
                    if (response.ok) {
                        const movie = await response.json();
                        displayMovie(movie);
                        loadHistory();
                    }
                } catch (error) {
                    console.error('Ошибка загрузки фильма:', error);
                }
            });
            
            historyList.appendChild(clone);
        });
    }
    
    async function loadStats() {
        try {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            movieCount.textContent = stats.total_movies;
            avgRating.textContent = stats.avg_rating;
            
            // Обновляем дату
            const now = new Date();
            lastUpdate.textContent = `Обновление: ${now.toLocaleDateString('ru-RU')}`;
            
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
            movieCount.textContent = '?';
            avgRating.textContent = '?';
        }
    }
    
    async function refreshMovies() {
        showLoading('Обновление базы фильмов...');
        
        try {
            const response = await fetch('/api/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                showNotification(`Добавлено ${result.message}! Всего фильмов: ${result.total}`);
                loadStats();
                loadGenres();
            } else {
                throw new Error('Ошибка обновления');
            }
        } catch (error) {
            showNotification('Ошибка при обновлении фильмов', 'error');
        } finally {
            hideLoading();
        }
    }
    
    function showWelcomeNotification() {
        if (!localStorage.getItem('welcome_shown')) {
            setTimeout(() => {
                showNotification('Добро пожаловать в КиноРулетку! 🎬');
                localStorage.setItem('welcome_shown', 'true');
            }, 1000);
        }
    }
    
    function showNotification(message, type = 'success') {
        // Удаляем предыдущие уведомления
        document.querySelectorAll('.notification').forEach(el => el.remove());
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Показываем уведомление
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Скрываем через 5 секунд
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 500);
        }, 5000);
    }
    
    function showLoading(text = 'Загрузка...') {
        let overlay = document.querySelector('.loading-overlay');
        
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="loading-spinner"></div>
                <div class="loading-text">${text}</div>
            `;
            document.body.appendChild(overlay);
        }
        
        setTimeout(() => overlay.classList.add('active'), 10);
    }
    
    function hideLoading() {
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 300);
        }
    }
    
    // Экспортируем функции для использования в HTML
    window.refreshMovies = refreshMovies;
});

// Добавляем стили для уведомлений
const style = document.createElement('style');
style.textContent = `
    .tmdb-link {
        display: inline-block;
        margin-top: 15px;
        padding: 8px 16px;
        background-color: #01b4e4;
        color: white;
        text-decoration: none;
        border-radius: 4px;
        font-size: 14px;
        transition: background-color 0.3s;
    }
    
    .tmdb-link:hover {
        background-color: #0099c3;
    }
    
    .tmdb-link i {
        margin-right: 5px;
    }
    
    .notification .notification-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .notification.success {
        background-color: var(--kp-green);
    }
    
    .notification.error {
        background-color: #ff4757;
    }
`;
document.head.appendChild(style);
