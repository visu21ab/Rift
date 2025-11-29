// Check authentication status on load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    
    // Setup event listeners after DOM is ready
    const loginBtnStep = document.getElementById('loginBtnStep');
    const logoutBtn = document.getElementById('logoutBtn');
    const playlistForm = document.getElementById('playlistForm');
    
    const connectToSpotify = () => {
        window.location.href = '/spotify/connect';
    };
    
    if (loginBtnStep) {
        loginBtnStep.addEventListener('click', connectToSpotify);
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
            
            // Validate sentence count for mood (max 5 sentences)
            const moodSentences = countSentences(mood);
            if (moodSentences > 5) {
                showError('Mood description must be 5 sentences or less. Please shorten your description.');
                return;
            }
            
            // Validate sentence count for playlist name (max 5 sentences)
            const playlistNameSentences = countSentences(playlistName);
            if (playlistNameSentences > 5) {
                showError('Playlist name must be 5 sentences or less. Please shorten your playlist name.');
                return;
            }
            
            const requestBody = {
                mood: mood,
                playlist_name: playlistName,
                track_count: trackCount
            };
            
            // Hide previous results and errors
            document.getElementById('resultsSection').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
            
            // Show loading indicator
            const loadingIndicator = document.getElementById('loadingIndicator');
            if (loadingIndicator) loadingIndicator.style.display = 'flex';
            
            // Show loading state
            const generateBtn = document.getElementById('generateBtn');
            if (!generateBtn) return;
            const btnText = generateBtn.querySelector('.btn-text');
            const btnLoader = generateBtn.querySelector('.btn-loader');
            
            if (btnText) btnText.style.display = 'none';
            if (btnLoader) btnLoader.style.display = 'inline-flex';
            generateBtn.disabled = true;
            
            try {
                const response = await fetch('/api/generate-playlist', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody)
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
                // Hide loading indicator
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                
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
        updateStepVisibility(data);
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

// Update step visibility based on Spotify connection
function updateStepVisibility(data) {
    const loginBtnStep = document.getElementById('loginBtnStep');
    
    if (data.spotify_connected) {
        // Hide the connect button when connected
        if (loginBtnStep) {
            loginBtnStep.style.display = 'none';
        }
    } else {
        // Show the connect button when not connected
        if (loginBtnStep) {
            loginBtnStep.style.display = 'inline-flex';
        }
    }
}

function updateUserHeader(data) {
    const userInfo = document.getElementById('userInfo');
    const topBannerIdentity = document.getElementById('topBannerIdentity');
    const topBannerCredits = document.getElementById('topBannerCredits');

    // Update header buttons
    if (userInfo) userInfo.style.display = 'flex';
    
    const displayName = data.spotify_display_name || data.email || 'User';
    if (topBannerIdentity) topBannerIdentity.textContent = displayName;
    if (typeof data.credits_remaining === 'number') {
        if (topBannerCredits) topBannerCredits.textContent = `${data.credits_remaining} credits`;
    }
}

// Display results
function displayResults(data) {
    // Update metrics (with safe access to prevent errors)
    const indieMetric = document.getElementById('indieMetric');
    const diversityMetric = document.getElementById('diversityMetric');
    const tracksMetric = document.getElementById('tracksMetric');
    
    if (indieMetric) {
        if (data.metrics && typeof data.metrics.indie_fraction === 'number') {
            indieMetric.textContent = `${data.metrics.indie_fraction}%`;
        } else {
            indieMetric.textContent = '—';
        }
    }
    
    if (diversityMetric) {
        if (data.metrics && typeof data.metrics.diversity_score === 'number') {
            diversityMetric.textContent = data.metrics.diversity_score.toFixed(2);
        } else {
            diversityMetric.textContent = '—';
        }
    }
    
    if (tracksMetric) {
        const requestedCount = typeof data.requested_track_count === 'number' ? data.requested_track_count : null;
        tracksMetric.textContent = requestedCount ? `${data.tracks_found}/${requestedCount}` : data.tracks_found;
    }
    const topBannerCredits = document.getElementById('topBannerCredits');
    const userCredits = document.getElementById('userCredits');
    if (typeof data.credits_remaining === 'number') {
        if (topBannerCredits) topBannerCredits.textContent = `${data.credits_remaining} credits`;
        if (userCredits) userCredits.textContent = `${data.credits_remaining} credits`;
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

// Count sentences in a text string
function countSentences(text) {
    if (!text || !text.trim()) {
        return 0;
    }
    // Split by sentence-ending punctuation followed by whitespace or end of string
    const sentences = text.trim().split(/[.!?]+(?:\s+|$)/).filter(s => s.trim());
    return sentences.length > 0 ? sentences.length : 1; // At least 1 if there's any text
}



