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
    
    // Состояние
    let selectedGenres = [];
    let genres = [];
    
    // Инициализация
    loadGenres();
    loadHistory();
    updateRatingValue();
    
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
        }
    }
    
    function renderGenreChips() {
        genreChips.innerHTML = '';
        genres.forEach(genre => {
            const chip = document.createElement('span');
            chip.className = 'genre-chip';
            chip.textContent = genre;
            chip.dataset.genre = genre;
            
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
        ratingEl.textContent = movie.rating_kp ? movie.rating_kp.toFixed(1) : '?';
        
        if (movie.rating_kp >= 7) ratingEl.classList.add('rating-high');
        else if (movie.rating_kp >= 5) ratingEl.classList.add('rating-medium');
        else ratingEl.classList.add('rating-low');
        
        // Основная информация
        clone.querySelector('.movie-title').textContent = movie.title_ru;
        clone.querySelector('.movie-year').textContent = movie.year;
        clone.querySelector('.movie-duration').textContent = movie.duration ? `${movie.duration} мин` : '';
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
            card.addEventListener('click', () => displayMovie(movie));
            
            historyList.appendChild(clone);
        });
    }
});
