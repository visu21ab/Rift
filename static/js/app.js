// Check authentication status on load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    
    // Setup event listeners after DOM is ready
    const loginBtn = document.getElementById('loginBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const playlistForm = document.getElementById('playlistForm');
    
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            window.location.href = '/spotify/connect';
        });
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            // Call logout endpoint to clear session
            window.location.href = '/logout';
        });
    }
    
    if (playlistForm) {
        playlistForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const mood = document.getElementById('mood').value.trim();
            const playlistName = document.getElementById('playlistName').value.trim() || 'AI Generated Playlist';
            const trackCountInput = document.getElementById('trackCount');
            const requestedTrackCount = trackCountInput ? parseInt(trackCountInput.value, 10) : 25;
            const trackCount = Math.max(1, Math.min(50, isNaN(requestedTrackCount) ? 25 : requestedTrackCount));

            if (!mood) {
                showError('Please enter a mood description');
                return;
            }
            
            // Hide previous results and errors
            document.getElementById('resultsSection').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
            
            // Show loading state
            const generateBtn = document.getElementById('generateBtn');
            if (!generateBtn) return;
            const btnText = generateBtn.querySelector('.btn-text');
            const btnLoader = generateBtn.querySelector('.btn-loader');
            
            if (btnText) btnText.style.display = 'none';
            if (btnLoader) btnLoader.style.display = 'inline-block';
            generateBtn.disabled = true;
            
            try {
                const response = await fetch('/api/generate-playlist', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        mood: mood,
                        playlist_name: playlistName,
                        track_count: trackCount
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to generate playlist');
                }
                
                // Show results
                displayResults(data);
                
            } catch (error) {
                showError(error.message);
            } finally {
                // Reset button state
                if (btnText) btnText.style.display = 'inline';
                if (btnLoader) btnLoader.style.display = 'none';
                generateBtn.disabled = false;
            }
        });
    }
});

// Check if user is authenticated
async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth-status');
        const data = await response.json();

        if (!data.authenticated) {
            window.location.href = '/login';
            return;
        }

        updateUserHeader(data);
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

function updateUserHeader(data) {
    const loginBtn = document.getElementById('loginBtn');
    const userInfo = document.getElementById('userInfo');
    const userName = document.getElementById('userName');
    const userCredits = document.getElementById('userCredits');

    if (userInfo) userInfo.style.display = 'flex';
    if (loginBtn) loginBtn.style.display = data.spotify_connected ? 'none' : 'inline-flex';
    if (userName) userName.textContent = data.spotify_display_name || data.email || 'User';
    if (userCredits && typeof data.credits_remaining === 'number') {
        userCredits.textContent = `Credits: ${data.credits_remaining}`;
    }
}

// Display results
function displayResults(data) {
    // Update metrics
    const indieMetric = document.getElementById('indieMetric');
    const diversityMetric = document.getElementById('diversityMetric');
    const tracksMetric = document.getElementById('tracksMetric');
    if (indieMetric) indieMetric.textContent = `${data.metrics.indie_fraction}%`;
    if (diversityMetric) diversityMetric.textContent = data.metrics.diversity_score.toFixed(2);
    if (tracksMetric) {
        const requestedCount = typeof data.requested_track_count === 'number' ? data.requested_track_count : null;
        tracksMetric.textContent = requestedCount ? `${data.tracks_found}/${requestedCount}` : data.tracks_found;
    }
    const userCredits = document.getElementById('userCredits');
    if (userCredits && typeof data.credits_remaining === 'number') {
        userCredits.textContent = `Credits: ${data.credits_remaining}`;
    }
    
    // Update Spotify link
    const spotifyLink = document.getElementById('spotifyLink');
    if (spotifyLink) spotifyLink.href = data.spotify_url;
    
    // Display tracks
    const tracksList = document.getElementById('tracksList');
    if (tracksList) {
        tracksList.innerHTML = '';
        
        if (data.tracks && data.tracks.length > 0) {
            data.tracks.forEach(track => {
                const trackItem = document.createElement('div');
                trackItem.className = 'track-item';
                trackItem.innerHTML = `
                    <div class="track-info">
                        <div class="track-name">${escapeHtml(track.track)}</div>
                        <div class="track-artist">${escapeHtml(track.artist)}</div>
                    </div>
                `;
                tracksList.appendChild(trackItem);
            });
        }
    }
    
    // Show results section
    const resultsSection = document.getElementById('resultsSection');
    if (resultsSection) {
        resultsSection.style.display = 'block';
        // Scroll to results
        resultsSection.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    if (!errorDiv) return;
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Scroll to error
    errorDiv.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center' 
    });
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

