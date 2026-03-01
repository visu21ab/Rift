// ============================================
// GSAP ScrollTrigger Animations
// ============================================
function initGSAPAnimations() {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;

    gsap.registerPlugin(ScrollTrigger);

    // Set default ease
    gsap.defaults({ ease: 'power3.out' });

    // Header fade in on load
    gsap.from('.header', {
        opacity: 0,
        y: -20,
        duration: 0.8,
        delay: 0.2
    });

    // Step sections: fade in + slide up with ScrollTrigger
    document.querySelectorAll('.step-section').forEach((section, i) => {
        gsap.from(section, {
            scrollTrigger: {
                trigger: section,
                start: 'top 85%',
                toggleActions: 'play none none none'
            },
            opacity: 0,
            y: 50,
            duration: 0.8,
            delay: i * 0.1
        });
    });

    // About section
    const aboutSection = document.querySelector('.about-section');
    if (aboutSection) {
        gsap.from(aboutSection, {
            scrollTrigger: {
                trigger: aboutSection,
                start: 'top 85%',
                toggleActions: 'play none none none'
            },
            opacity: 0,
            y: 40,
            duration: 0.8
        });
    }

    // Connect buttons stagger
    const connectButtons = document.querySelectorAll('.connect-buttons .btn-primary');
    if (connectButtons.length) {
        gsap.fromTo(connectButtons, {
            opacity: 0,
            y: 20,
            scale: 0.97
        }, {
            opacity: 1,
            y: 0,
            scale: 1,
            duration: 0.6,
            stagger: 0.12,
            delay: 0.5
        });
    }

    // Button hover scale effects
    document.querySelectorAll('.btn-primary').forEach(btn => {
        btn.addEventListener('mouseenter', () => {
            gsap.to(btn, { scale: 1.02, duration: 0.2, ease: 'power2.out' });
        });
        btn.addEventListener('mouseleave', () => {
            gsap.to(btn, { scale: 1, duration: 0.3, ease: 'power2.out' });
        });
    });
}

// Animate track items when results appear
function animateTrackItems() {
    if (typeof gsap === 'undefined') return;

    const trackItems = document.querySelectorAll('.track-item');
    if (trackItems.length) {
        gsap.from(trackItems, {
            opacity: 0,
            y: 16,
            duration: 0.4,
            stagger: 0.04,
            ease: 'power2.out',
            delay: 0.2
        });
    }
}

// Animate metrics row
function animateMetrics() {
    if (typeof gsap === 'undefined') return;

    const metricItems = document.querySelectorAll('.metric-item');
    if (metricItems.length) {
        gsap.from(metricItems, {
            opacity: 0,
            y: 20,
            scale: 0.95,
            duration: 0.5,
            stagger: 0.1,
            ease: 'power2.out'
        });
    }
}

// Animate playlists list items
function animatePlaylistItems() {
    if (typeof gsap === 'undefined') return;

    const items = document.querySelectorAll('.playlist-item');
    if (items.length) {
        gsap.from(items, {
            opacity: 0,
            y: 16,
            duration: 0.4,
            stagger: 0.05,
            ease: 'power2.out'
        });
    }
}

// Check authentication status on load
document.addEventListener('DOMContentLoaded', () => {
    // Initialize GSAP animations
    initGSAPAnimations();

    checkAuthStatus();
    
    // Check for subscription success/cancel messages
    const body = document.body;
    if (body.getAttribute('data-subscription-success') === 'true') {
        showError('Subscription successful! You now have access to 25 playlists per month.', 'success');
        // Refresh auth status to update UI
        setTimeout(() => checkAuthStatus(), 500);
        // Remove attribute to prevent showing message again
        body.removeAttribute('data-subscription-success');
    }
    if (body.getAttribute('data-subscription-canceled') === 'true') {
        showError('Subscription canceled. You can subscribe again anytime.', 'success');
        body.removeAttribute('data-subscription-canceled');
    }
    
    // Setup event listeners after DOM is ready
    const logoutBtn = document.getElementById('logoutBtn');
    const viewPlaylistsBtn = document.getElementById('viewPlaylistsBtn');
    const playlistForm = document.getElementById('playlistForm');
    if (viewPlaylistsBtn) {
        viewPlaylistsBtn.addEventListener('click', () => {
            const playlistsSection = document.getElementById('myPlaylistsSection');
            const stepMood = document.getElementById('stepMood');
            const stepResults = document.getElementById('stepResults');
            
            if (playlistsSection) {
                if (playlistsSection.style.display === 'none') {
                    playlistsSection.style.display = 'block';
                    if (stepMood) stepMood.style.display = 'none';
                    if (stepResults) stepResults.style.display = 'none';
                    fetchPlaylists();
                } else {
                    playlistsSection.style.display = 'none';
                    if (stepMood) stepMood.style.display = 'block';
                }
            }
        });
    }
    
    const connectSpotifyBtn = document.getElementById('connectSpotifyBtn');
    const connectSoundCloudBtn = document.getElementById('connectSoundCloudBtn');

    if (connectSpotifyBtn) {
        connectSpotifyBtn.addEventListener('click', () => {
            if (!connectSpotifyBtn.classList.contains('btn-connected')) {
                window.location.href = '/spotify/connect';
            }
        });
    }
    if (connectSoundCloudBtn) {
        connectSoundCloudBtn.addEventListener('click', () => {
            if (!connectSoundCloudBtn.classList.contains('btn-connected')) {
                window.location.href = '/soundcloud/connect';
            }
        });
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            // Call logout endpoint to clear session
            window.location.href = '/logout';
        });
    }
    
    // Upgrade to premium button handler
    const upgradeToPremiumBtn = document.getElementById('upgradeToPremiumBtn');
    if (upgradeToPremiumBtn) {
        upgradeToPremiumBtn.addEventListener('click', handleSubscribe);
    }
    
    // Cancel subscription button handler
    const cancelSubscriptionBtn = document.getElementById('cancelSubscriptionBtn');
    if (cancelSubscriptionBtn) {
        cancelSubscriptionBtn.addEventListener('click', handleCancelSubscription);
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
            
            // Determine selected provider
            const providerRadio = document.querySelector('input[name="provider"]:checked');
            const provider = providerRadio ? providerRadio.value : null;

            const requestBody = {
                mood: mood,
                playlist_name: playlistName,
                track_count: trackCount
            };
            if (provider) {
                requestBody.provider = provider;
            }
            
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
                    // Check if upgrade is required
                    if (data.upgrade_required) {
                        showUpgradePrompt(data.error || 'You have reached your monthly limit. Upgrade to premium for 25 playlists per month.');
                    } else {
                        throw new Error(data.error || 'Failed to generate playlist');
                    }
                    return;
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

// Update step visibility based on music service connections
function updateStepVisibility(data) {
    const connectSpotifyBtn = document.getElementById('connectSpotifyBtn');
    const connectSoundCloudBtn = document.getElementById('connectSoundCloudBtn');

    updateConnectButton(connectSpotifyBtn, data.spotify_connected, 'Spotify', '/spotify/disconnect');
    updateConnectButton(connectSoundCloudBtn, data.soundcloud_connected, 'SoundCloud', '/soundcloud/disconnect');

    // Update service selector
    updateServiceSelector(data.spotify_connected, data.soundcloud_connected);
}

function updateConnectButton(btn, isConnected, serviceName, disconnectUrl) {
    if (!btn) return;

    // Remove any existing disconnect link
    const existingDisconnect = btn.parentElement.querySelector('.btn-disconnect[data-service="' + serviceName + '"]');
    if (existingDisconnect) existingDisconnect.remove();

    if (isConnected) {
        btn.classList.add('btn-connected');
        btn.innerHTML = '<span class="btn-checkmark">\u2713</span> Connected to ' + serviceName;
        // Add disconnect link below
        const disconnectLink = document.createElement('button');
        disconnectLink.className = 'btn-disconnect';
        disconnectLink.setAttribute('data-service', serviceName);
        disconnectLink.textContent = 'Disconnect';
        disconnectLink.addEventListener('click', (e) => {
            e.stopPropagation();
            window.location.href = disconnectUrl;
        });
        btn.parentElement.insertBefore(disconnectLink, btn.nextSibling);
    } else {
        btn.classList.remove('btn-connected');
        btn.textContent = 'Connect ' + serviceName;
    }
}

function updateServiceSelector(spotifyConnected, soundcloudConnected) {
    const selector = document.getElementById('serviceSelector');
    const spotifyRadio = document.getElementById('providerSpotify');
    const soundcloudRadio = document.getElementById('providerSoundCloud');
    if (!selector || !spotifyRadio || !soundcloudRadio) return;

    const spotifyLabel = selector.querySelector('label[for="providerSpotify"]');
    const soundcloudLabel = selector.querySelector('label[for="providerSoundCloud"]');

    if (!spotifyConnected && !soundcloudConnected) {
        selector.style.display = 'none';
        return;
    }

    // Show/hide options based on connection status
    spotifyRadio.style.display = spotifyConnected ? 'none' : 'none';
    if (spotifyLabel) spotifyLabel.style.display = spotifyConnected ? 'inline-flex' : 'none';
    soundcloudRadio.style.display = soundcloudConnected ? 'none' : 'none';
    if (soundcloudLabel) soundcloudLabel.style.display = soundcloudConnected ? 'inline-flex' : 'none';

    // Auto-select logic
    if (spotifyConnected && soundcloudConnected) {
        selector.style.display = 'flex';
        if (!spotifyRadio.checked && !soundcloudRadio.checked) {
            spotifyRadio.checked = true;
        }
    } else if (spotifyConnected) {
        // Only one service — auto-select and hide selector
        spotifyRadio.checked = true;
        soundcloudRadio.checked = false;
        selector.style.display = 'none';
    } else {
        soundcloudRadio.checked = true;
        spotifyRadio.checked = false;
        selector.style.display = 'none';
    }
}

function updateUserHeader(data) {
    const userInfo = document.getElementById('userInfo');
    const viewPlaylistsBtn = document.getElementById('viewPlaylistsBtn');
    const topBannerIdentity = document.getElementById('topBannerIdentity');
    const topBannerPlan = document.getElementById('topBannerPlan');
    const topBannerCredits = document.getElementById('topBannerCredits');
    const cancelSubscriptionBtn = document.getElementById('cancelSubscriptionBtn');
    const upgradeToPremiumBtn = document.getElementById('upgradeToPremiumBtn');

    // Update header buttons
    if (userInfo) userInfo.style.display = 'flex';
    if (viewPlaylistsBtn && data.authenticated) {
        viewPlaylistsBtn.style.display = 'inline-block';
    }
    
    const displayName = data.spotify_display_name || data.soundcloud_display_name || data.email || 'User';
    if (topBannerIdentity) topBannerIdentity.textContent = displayName;
    
    // Update subscription plan display
    if (topBannerPlan) {
        const plan = data.subscription_plan === 'premium' ? 'Premium' : 'Trial';
        topBannerPlan.textContent = plan;
    }
    
    // Show/hide upgrade to premium button for trial users
    if (upgradeToPremiumBtn) {
        // Show for trial users (not premium and not admin)
        // Handle 'trial', 'free', undefined, null, or any non-premium value
        const isPremium = data.subscription_plan === 'premium';
        const shouldShow = !isPremium && !data.is_admin;
        if (shouldShow) {
            upgradeToPremiumBtn.style.display = 'block';
        } else {
            upgradeToPremiumBtn.style.display = 'none';
        }
    }
    
    // Show/hide cancel subscription button for premium users
    if (cancelSubscriptionBtn) {
        if (data.subscription_plan === 'premium' && !data.is_admin) {
            cancelSubscriptionBtn.style.display = 'block';
        } else {
            cancelSubscriptionBtn.style.display = 'none';
        }
    }
    
    // Update playlist usage display (x/y format)
    if (topBannerCredits) {
        if (data.is_admin || data.monthly_limit === null || data.monthly_limit === undefined) {
            // Admins have unlimited playlists
            topBannerCredits.textContent = `${data.playlists_this_month || 0} playlists (unlimited)`;
        } else if (typeof data.playlists_this_month === 'number' && typeof data.monthly_limit === 'number') {
            topBannerCredits.textContent = `${data.playlists_this_month}/${data.monthly_limit} playlists`;
        } else if (typeof data.playlists_remaining === 'number') {
            // Fallback if monthly data not available
            topBannerCredits.textContent = `${data.playlists_remaining} playlists`;
        }
    }
}

async function fetchPlaylists() {
    try {
        const response = await fetch('/api/my-playlists');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch playlists');
        }
        
        displayPlaylists(data.playlists || []);
    } catch (error) {
        console.error('Error fetching playlists:', error);
        const playlistsList = document.getElementById('playlistsList');
        if (playlistsList) {
            playlistsList.innerHTML = `<p style="text-align: center; color: var(--text-muted);">Failed to load playlists. Please try again.</p>`;
        }
    }
}

function displayPlaylists(playlists) {
    const playlistsList = document.getElementById('playlistsList');
    if (!playlistsList) return;
    
    if (playlists.length === 0) {
        playlistsList.innerHTML = `<p style="text-align: center; color: var(--text-muted);">No playlists yet. Create your first playlist above!</p>`;
        return;
    }
    
    playlistsList.innerHTML = '';
    
    playlists.forEach(playlist => {
        const playlistItem = document.createElement('div');
        playlistItem.className = 'playlist-item';
        playlistItem.innerHTML = `
            <div class="playlist-info">
                <a href="${playlist.playlist_url || playlist.spotify_url || playlist.soundcloud_url}" target="_blank" class="playlist-name-link">
                    ${escapeHtml(playlist.name || 'Untitled Playlist')}
                </a>
                <div class="playlist-date">${new Date(playlist.created_at).toLocaleDateString()}</div>
            </div>
        `;
        playlistsList.appendChild(playlistItem);
    });

    // Trigger GSAP stagger animation for playlist items
    animatePlaylistItems();
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
    // Update usage display after playlist creation
    const topBannerCredits = document.getElementById('topBannerCredits');
    if (topBannerCredits && typeof data.playlists_this_month === 'number' && typeof data.monthly_limit === 'number') {
        topBannerCredits.textContent = `${data.playlists_this_month}/${data.monthly_limit} playlists`;
    } else if (topBannerCredits && typeof data.playlists_remaining === 'number') {
        topBannerCredits.textContent = `${data.playlists_remaining} playlists`;
    }
    
    // Refresh auth status to update all UI elements
    checkAuthStatus();
    
    // Update playlist link (works for both Spotify and SoundCloud)
    const playlistLink = document.getElementById('playlistLink');
    if (playlistLink) {
        const url = data.playlist_url || data.spotify_url || data.soundcloud_url;
        playlistLink.href = url;
        if (data.spotify_url) {
            playlistLink.textContent = 'Open in Spotify';
        } else if (data.soundcloud_url) {
            playlistLink.textContent = 'Open in SoundCloud';
        }
        if (data.playlist_id) {
            playlistLink.setAttribute('data-playlist-id', data.playlist_id);
        }
    }
    
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
        // Trigger GSAP animations for results
        animateMetrics();
        animateTrackItems();
    }
}

// Show error message
function showError(message, type = 'error') {
    const errorDiv = document.getElementById('errorMessage');
    if (!errorDiv) return;
    
    // Clear any HTML content and set text
    errorDiv.textContent = message;
    errorDiv.className = type === 'success' ? 'error-message success-message' : 'error-message';
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

// Handle subscription checkout
async function handleSubscribe() {
    const upgradeBtn = document.getElementById('upgradeToPremiumBtn');
    if (!upgradeBtn) return;
    
    // Disable button and show loading state
    upgradeBtn.disabled = true;
    const originalText = upgradeBtn.textContent;
    upgradeBtn.textContent = 'Loading...';
    
    try {
        const response = await fetch('/api/create-checkout-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create checkout session');
        }
        
        // Redirect to Stripe Checkout
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            throw new Error('No checkout URL received');
        }
    } catch (error) {
        showError(error.message);
        upgradeBtn.disabled = false;
        upgradeBtn.textContent = originalText;
    }
}

// Handle cancel subscription
async function handleCancelSubscription() {
    const cancelBtn = document.getElementById('cancelSubscriptionBtn');
    if (!cancelBtn) return;
    
    // Confirm cancellation
    if (!confirm('Are you sure you want to cancel your subscription? You will continue to have access until the end of your billing period, then be downgraded to the trial plan (3 playlists per month).')) {
        return;
    }
    
    // Disable button and show loading state
    cancelBtn.disabled = true;
    const originalText = cancelBtn.textContent;
    cancelBtn.textContent = 'Canceling...';
    
    try {
        const response = await fetch('/api/cancel-subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to cancel subscription');
        }
        
        // Show success message
        showError('Subscription will be canceled at the end of your billing period. You will be downgraded to trial plan.', 'success');
        
        // Refresh auth status to update UI
        setTimeout(() => {
            checkAuthStatus();
        }, 1000);
    } catch (error) {
        showError(error.message);
    } finally {
        cancelBtn.disabled = false;
        cancelBtn.textContent = originalText;
    }
}

// Show upgrade prompt with subscribe button
function showUpgradePrompt(message) {
    const errorDiv = document.getElementById('errorMessage');
    if (!errorDiv) return;
    
    errorDiv.innerHTML = `
        <div style="text-align: center;">
            <p style="margin-bottom: 1rem;">${escapeHtml(message)}</p>
            <button class="btn-primary" onclick="handleSubscribe()" style="margin-top: 0.5rem;">
                Subscribe to Premium (49 SEK/month)
            </button>
        </div>
    `;
    errorDiv.style.display = 'block';
    
    // Scroll to error
    errorDiv.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center' 
    });
}




