/*
 * Pychronia media players, built on Plyr (static/libs/plyr/).
 *
 * - PychroniaMedia.init(): enhances <audio>/<video> elements having the "pychronia-media-element"
 *   class (idempotent, called by each server-generated player snippet, and on DOM ready).
 * - PychroniaMedia.PersonalRadio: looping webradio playlist (popup and webradio page), which
 *   periodically polls the server for new radio spots.
 * - PychroniaMedia.PublicRadio: "radio station" player, which consumes the global queue of
 *   radio spots one by one, notifying the server when each one has been broadcast.
 *
 * Both radios are designed to never get stuck: all network calls have timeouts and are retried
 * forever, broken or stalled audio files are skipped, and a watchdog restarts playback if needed.
 *
 * Plain ES5 + fetch/Promise, no jQuery dependency.
 */
(function (window, document) {
    "use strict";

    var scriptUrl = document.currentScript ? document.currentScript.src : null;
    var ICON_URL = scriptUrl ? new URL("../libs/plyr/plyr.svg", scriptUrl).href : undefined;

    var FETCH_TIMEOUT_MS = 10000;
    var WATCHDOG_PERIOD_MS = 5000;
    var STALL_TIMEOUT_MS = 30000;  // max time without playback progress, before skipping a spot

    var i18n = {};  // Plyr labels, see setI18n()

    function log() {
        if (window.console && console.info) {
            console.info.apply(console, ["[PychroniaMedia]"].concat(Array.prototype.slice.call(arguments)));
        }
    }

    function buildPlyrOptions(media) {
        var isVideo = (media.tagName === "VIDEO");
        return {
            iconUrl: ICON_URL,
            i18n: i18n,
            controls: isVideo ?
                ["play-large", "play", "progress", "current-time", "duration", "mute", "volume", "captions",
                 "settings", "fullscreen"] :
                ["play", "progress", "current-time", "duration", "mute", "volume"],
            settings: ["captions", "speed"],
            hideControls: isVideo,
            invertTime: false,
            resetOnEnd: !isVideo,
            keyboard: {focused: true, global: false},
            tooltips: {controls: true, seek: true},
            captions: {active: false, language: "auto", update: true},
            storage: {enabled: true, key: "pychronia_plyr"}  // remembers volume across pages
        };
    }

    function createPlayer(media, extraOptions) {
        if (!window.Plyr) {
            return null;  // native browser controls remain usable
        }
        var options = buildPlyrOptions(media);
        Object.keys(extraOptions || {}).forEach(function (key) {
            options[key] = extraOptions[key];
        });
        try {
            return new window.Plyr(media, options);
        } catch (e) {
            log("Plyr initialization failed", e);
            return null;
        }
    }

    /* Calls media.play(), and calls onBlocked() if the browser forbids autoplay. */
    function tryPlay(media, onBlocked, onFailure) {
        var promise;
        try {
            promise = media.play();
        } catch (e) {
            promise = null;
        }
        if (promise && typeof promise.then === "function") {
            promise.then(null, function (error) {
                if (error && error.name === "NotAllowedError") {
                    if (onBlocked) onBlocked(error);
                } else if (error && error.name === "AbortError") {
                    // play() was interrupted by a new load(), that's expected when switching spots
                } else if (onFailure) {
                    onFailure(error);  // eg. NotSupportedError, for unplayable files
                }
            });
        }
    }

    /* Only one standard media player plays at a time, on a page. */
    function pauseOtherPlayers(currentMedia) {
        var all = document.querySelectorAll("audio, video");
        Array.prototype.forEach.call(all, function (media) {
            if (media !== currentMedia && !media.paused && media.hasAttribute("data-pychronia-media")) {
                media.pause();
            }
        });
    }

    function init(root) {
        root = root || document;
        var elements = root.querySelectorAll("audio.pychronia-media-element, video.pychronia-media-element");
        Array.prototype.forEach.call(elements, function (media) {
            if (media.hasAttribute("data-pychronia-media")) {
                return;  // already initialized
            }
            media.setAttribute("data-pychronia-media", "1");
            createPlayer(media);
            media.addEventListener("play", function () {
                pauseOtherPlayers(media);
            });
            if (media.getAttribute("data-autostart") === "true") {
                tryPlay(media);  // silently does nothing if the browser forbids autoplay
            }
        });
    }

    function setI18n(labels) {
        Object.keys(labels).forEach(function (key) {
            i18n[key] = labels[key];
        });
    }

    /* fetch() with a timeout, so that a hung request never blocks a polling loop. */
    function fetchWithTimeout(url, options) {
        options = options || {};
        var controller = window.AbortController ? new AbortController() : null;
        var timer = null;
        if (controller) {
            options.signal = controller.signal;
            timer = setTimeout(function () {
                controller.abort();
            }, FETCH_TIMEOUT_MS);
        }
        options.credentials = "same-origin";
        options.cache = "no-store";
        return window.fetch(url, options).then(function (response) {
            if (timer) clearTimeout(timer);
            if (!response.ok) {
                throw new Error("HTTP error " + response.status + " for " + url);
            }
            return response;
        }, function (error) {
            if (timer) clearTimeout(timer);
            throw error;
        });
    }

    function addQueryParams(url, params) {
        var query = Object.keys(params).map(function (key) {
            return encodeURIComponent(key) + "=" + encodeURIComponent(params[key]);
        }).join("&");
        return url + (url.indexOf("?") >= 0 ? "&" : "?") + query;
    }


    /*
     * Common base of radio controllers: owns an <audio> element, the "start" button shown when
     * the browser forbids autoplay, the status line, and the stall watchdog.
     *
     * Subclasses must implement onTrackEnded(), onTrackFailed(reason) and onWatchdogTick().
     */
    function BaseRadio(container, options) {
        this.container = container;
        this.options = options;
        this.labels = options.labels || {};
        this.media = container.querySelector("audio");
        this.startButton = container.querySelector(".radio-start-button");
        this.statusElement = container.querySelector(".radio-status");
        container.pychroniaRadio = this;  // handy for debugging

        this.wantPlaying = true;  // false once the user explicitly pauses the radio
        this.blocked = false;  // true while the browser forbids autoplay (until a user gesture)
        this.switching = false;  // true while we programmatically change the audio source
        this.currentUrl = null;

        this.lastProgressPosition = -1;
        this.lastProgressAt = Date.now();

        this.media.setAttribute("data-pychronia-media", "1");  // participates in pauseOtherPlayers()
        this.player = createPlayer(this.media, {resetOnEnd: false});
        this._bindEvents();

        var self = this;
        setInterval(function () {
            self._watchdog();
        }, WATCHDOG_PERIOD_MS);
    }

    BaseRadio.prototype._bindEvents = function () {
        var self = this, media = this.media;

        media.addEventListener("ended", function () {
            self.currentUrl = null;
            self.onTrackEnded();
        });
        media.addEventListener("error", function () {
            if (!self.currentUrl) {
                return;  // error of an emptied media element, not of a real spot
            }
            var code = media.error ? media.error.code : "?";
            self.currentUrl = null;
            self.onTrackFailed("media error " + code);
        });
        media.addEventListener("playing", function () {
            self.switching = false;
            self._setBlocked(false);
            self._markProgress();
        });
        media.addEventListener("timeupdate", function () {
            if (media.currentTime !== self.lastProgressPosition) {
                self._markProgress();
            }
        });
        media.addEventListener("play", function () {
            pauseOtherPlayers(media);
            if (!self.switching) {
                self.wantPlaying = true;  // user pressed "play"
                self._setBlocked(false);
            }
        });
        media.addEventListener("pause", function () {
            if (!self.switching && !media.ended) {
                self.wantPlaying = false;  // user pressed "pause"
            }
        });

        if (this.startButton) {
            this.startButton.addEventListener("click", function (event) {
                event.preventDefault();
                self.wantPlaying = true;
                self._setBlocked(false);
                self.onStartButtonClicked();
            });
        }
    };

    BaseRadio.prototype._markProgress = function () {
        this.lastProgressPosition = this.media.currentTime;
        this.lastProgressAt = Date.now();
    };

    BaseRadio.prototype._setBlocked = function (blocked) {
        this.blocked = blocked;
        if (this.startButton) {
            this.startButton.style.display = blocked ? "" : "none";
        }
        this.container.classList.toggle("radio-blocked", blocked);
    };

    BaseRadio.prototype.setStatus = function (text) {
        if (this.statusElement) {
            this.statusElement.textContent = text || "";
        }
    };

    BaseRadio.prototype.isAudible = function () {
        return Boolean(this.currentUrl && !this.media.paused && !this.blocked);
    };

    /* Loads an audio file, and plays it unless the user paused the radio. */
    BaseRadio.prototype.loadAndPlay = function (url) {
        var self = this;
        this.switching = true;
        this.currentUrl = url;
        this._markProgress();
        this.media.src = url;
        this.media.load();
        this.resume();
        setTimeout(function () {
            self.switching = false;  // in case "playing" never comes
        }, 3000);
    };

    BaseRadio.prototype.resume = function () {
        var self = this, url = this.currentUrl;
        if (!this.wantPlaying || this.blocked || !url) {
            return;
        }
        tryPlay(this.media,
            function () {
                log("autoplay forbidden by browser, waiting for a user gesture");
                self._setBlocked(true);
            },
            function (error) {
                setTimeout(function () {
                    // the "error" event usually handles that case, unless it got lost
                    if (self.currentUrl === url && self.media.paused) {
                        self.currentUrl = null;
                        self.onTrackFailed("play() failed: " + error);
                    }
                }, 2000);
            });
    };

    BaseRadio.prototype.onStartButtonClicked = function () {
        this.resume();
    };

    /* Resumes playback after unexpected pauses, and skips spots which don't progress anymore. */
    BaseRadio.prototype._watchdog = function () {
        var media = this.media;
        if (this.currentUrl && this.wantPlaying && !this.blocked) {
            if (media.paused && !media.ended && !this.switching) {
                log("radio unexpectedly paused, resuming");
                this.resume();
            } else if (!media.paused && media.currentTime === this.lastProgressPosition &&
                       Date.now() - this.lastProgressAt > STALL_TIMEOUT_MS) {
                log("radio stalled, skipping spot", this.currentUrl);
                this.currentUrl = null;
                media.pause();
                this.onTrackFailed("stalled");
            }
        }
        this.onWatchdogTick();
    };


    /*
     * Personal webradio: loops over the whole current playlist, and polls the server for changes.
     *
     * Expected JSON: {"playlist": [{"id": ..., "url": ..., "title": ...}, ...]}
     */
    function PersonalRadio(container, options) {
        this.playlistUrl = options.playlistUrl;
        this.pollDelayMs = options.pollDelayMs || 20000;
        this.gapMs = (options.gapMs !== undefined) ? options.gapMs : 1500;
        this.listElement = container.querySelector(".radio-playlist");

        this.playlist = null;  // null until first successfully loaded
        this.currentId = null;
        this.loopId = null;  // last spot played in the normal loop order (i.e. not as a priority spot)
        this.loopIndex = 0;
        this.priorityIds = [];  // newly arrived spots, played first, then the loop resumes where it was
        this.consecutiveFailures = 0;
        this.idleUntil = 0;  // timestamp before which the watchdog must not restart the radio
        this.nextTimer = null;
        this.pollTimer = null;

        BaseRadio.call(this, container, options);
        this.setStatus(this.labels.loading);
        this.poll();
    }

    PersonalRadio.prototype = Object.create(BaseRadio.prototype);
    PersonalRadio.prototype.constructor = PersonalRadio;

    PersonalRadio.prototype.poll = function () {
        var self = this;
        clearTimeout(this.pollTimer);
        this.pollTimer = null;
        var url = addQueryParams(this.playlistUrl, {listening: this.isAudible() ? 1 : 0});
        fetchWithTimeout(url)
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                self.updatePlaylist(data.playlist || []);
            })
            .then(null, function (error) {
                log("playlist polling failed, will retry", error);
                if (self.playlist === null) {
                    self.setStatus(self.labels.connectionProblem);
                }
            })
            .then(function () {
                clearTimeout(self.pollTimer);
                self.pollTimer = setTimeout(function () {
                    self.poll();
                }, self.pollDelayMs);
            });
    };

    PersonalRadio.prototype._indexOfId = function (id) {
        for (var i = 0; i < this.playlist.length; i++) {
            if (this.playlist[i].id === id) {
                return i;
            }
        }
        return -1;
    };

    PersonalRadio.prototype.updatePlaylist = function (newPlaylist) {
        var self = this;
        var isInitialLoad = (this.playlist === null);
        var knownIds = {};
        (this.playlist || []).forEach(function (item) {
            knownIds[item.id] = true;
        });

        this.playlist = newPlaylist.filter(function (item) {
            return item && item.url;
        });

        if (!isInitialLoad) {
            this.playlist.forEach(function (item) {
                if (!knownIds[item.id] && self.priorityIds.indexOf(item.id) < 0) {
                    log("new radio spot arrived", item.id);
                    self.priorityIds.push(item.id);
                }
            });
        }
        this.priorityIds = this.priorityIds.filter(function (id) {
            return self._indexOfId(id) >= 0;
        });

        this.render();

        if (!this.currentUrl && !this.nextTimer) {
            // the radio is idle (empty playlist, or all spots failed): we (re)start it
            this.playNext();
        }
    };

    /* Chooses and plays the next spot: new spots first, then the following one in the loop. */
    PersonalRadio.prototype.playNext = function () {
        clearTimeout(this.nextTimer);
        this.nextTimer = null;

        if (!this.playlist || !this.playlist.length) {
            this.currentId = null;
            this.setStatus(this.playlist ? this.labels.empty : this.labels.loading);
            this.render();
            return;  // next poll will restart the radio
        }

        if (this.consecutiveFailures >= this.playlist.length) {
            // every spot failed: we wait for the next poll, instead of looping on errors
            this.consecutiveFailures = 0;
            this.idleUntil = Date.now() + this.pollDelayMs;
            this.currentId = null;
            this.setStatus(this.labels.connectionProblem);
            this.render();
            return;
        }

        var index, isPriority = false;
        if (this.priorityIds.length) {
            index = this._indexOfId(this.priorityIds.shift());
            isPriority = true;
        } else if (this.loopId !== null && this._indexOfId(this.loopId) >= 0) {
            index = this._indexOfId(this.loopId) + 1;
        } else {
            index = this.loopIndex;  // last looped spot was removed, following ones shifted back
        }
        if (index < 0 || index >= this.playlist.length) {
            index = 0;  // we loop over the playlist
            isPriority = false;
        }
        this.playIndex(index, isPriority);
    };

    PersonalRadio.prototype.playIndex = function (index, isPriority) {
        var item = this.playlist[index];
        clearTimeout(this.nextTimer);
        this.nextTimer = null;
        if (!isPriority) {
            this.loopIndex = index;
            this.loopId = item.id;
        }
        this.currentId = item.id;
        var position = this.priorityIds.indexOf(item.id);
        if (position >= 0) {
            this.priorityIds.splice(position, 1);
        }
        this.setStatus(item.title);
        this.render();
        this.loadAndPlay(item.url);
    };

    PersonalRadio.prototype._scheduleNext = function (delayMs) {
        var self = this;
        clearTimeout(this.nextTimer);
        this.nextTimer = setTimeout(function () {
            self.nextTimer = null;
            self.playNext();
        }, delayMs);
    };

    PersonalRadio.prototype.onTrackEnded = function () {
        this.consecutiveFailures = 0;
        this._scheduleNext(this.gapMs);
    };

    PersonalRadio.prototype.onTrackFailed = function (reason) {
        log("radio spot failed", this.currentId, reason);
        this.consecutiveFailures += 1;
        this._scheduleNext(3000);
    };

    PersonalRadio.prototype.onStartButtonClicked = function () {
        if (this.currentUrl) {
            this.resume();
        } else {
            this.playNext();
        }
    };

    PersonalRadio.prototype.onWatchdogTick = function () {
        if (this.wantPlaying && !this.currentUrl && !this.nextTimer && this.playlist && this.playlist.length &&
            Date.now() >= this.idleUntil) {
            this.playNext();  // should never happen, but we never let the radio idle with spots available
        }
    };

    PersonalRadio.prototype.render = function () {
        var self = this;
        if (!this.listElement) {
            return;
        }
        this.listElement.textContent = "";  // removes previous entries
        (this.playlist || []).forEach(function (item, index) {
            var li = document.createElement("li");
            var link = document.createElement("a");
            link.href = "#";
            link.textContent = item.title;
            link.addEventListener("click", function (event) {
                event.preventDefault();
                self.wantPlaying = true;
                self._setBlocked(false);
                self.consecutiveFailures = 0;
                self.playIndex(index);
            });
            li.appendChild(link);
            if (item.id === self.currentId) {
                li.className = "current";
            } else if (self.priorityIds.indexOf(item.id) >= 0) {
                li.className = "novelty";
            }
            self.listElement.appendChild(li);
        });
    };


    /*
     * Public radio station: plays the head of the global radio queue, then notifies the server,
     * which removes it from the queue.
     *
     * Expected JSON from nextUrl: [audio_id, file_url] or [null, null].
     */
    function PublicRadio(container, options) {
        this.nextUrl = options.nextUrl;
        this.notifyUrl = options.notifyUrl;
        this.pollDelayMs = options.pollDelayMs || 5000;
        this.maxFailuresPerSpot = options.maxFailuresPerSpot || 3;

        this.currentId = null;
        this.failures = {};
        this.busy = false;  // a request is in progress, or scheduled
        this.timer = null;

        BaseRadio.call(this, container, options);
        this.setStatus(this.labels.waiting);
        this._schedule(this.fetchNext, 500);
    }

    PublicRadio.prototype = Object.create(BaseRadio.prototype);
    PublicRadio.prototype.constructor = PublicRadio;

    PublicRadio.prototype._schedule = function (method, delayMs) {
        var self = this;
        clearTimeout(this.timer);
        this.busy = true;
        this.timer = setTimeout(function () {
            self.timer = null;
            method.call(self);
        }, delayMs);
    };

    PublicRadio.prototype.fetchNext = function () {
        var self = this;
        this.busy = true;
        fetchWithTimeout(this.nextUrl)
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                var audioId = data && data[0], fileUrl = data && data[1];
                if (audioId && fileUrl) {
                    self.busy = false;
                    self.currentId = audioId;
                    self.setStatus(self.labels.broadcasting);
                    self.loadAndPlay(fileUrl);
                } else {
                    self.currentId = null;
                    self.setStatus(self.labels.waiting);
                    self._schedule(self.fetchNext, self.pollDelayMs);
                }
            })
            .then(null, function (error) {
                log("next spot fetching failed, will retry", error);
                self._schedule(self.fetchNext, self.pollDelayMs);
            });
    };

    PublicRadio.prototype.notifyFinished = function (audioId) {
        var self = this;
        this.busy = true;
        fetchWithTimeout(addQueryParams(this.notifyUrl, {audio_id: audioId}))
            .then(function () {
                delete self.failures[audioId];
                self.fetchNext();
            }, function (error) {
                log("notification failed, will retry", error);
                self._schedule(function () {
                    self.notifyFinished(audioId);
                }, self.pollDelayMs);
            });
    };

    PublicRadio.prototype.onTrackEnded = function () {
        this.notifyFinished(this.currentId);
    };

    PublicRadio.prototype.onTrackFailed = function (reason) {
        var audioId = this.currentId;
        this.failures[audioId] = (this.failures[audioId] || 0) + 1;
        log("radio spot failed", audioId, reason, "attempt", this.failures[audioId]);
        if (this.failures[audioId] >= this.maxFailuresPerSpot) {
            log("giving up on broken radio spot", audioId);
            this.notifyFinished(audioId);  // else the whole queue would be stuck behind it
        } else {
            this._schedule(this.fetchNext, this.pollDelayMs);
        }
    };

    PublicRadio.prototype.onWatchdogTick = function () {
        if (!this.currentUrl && !this.busy) {
            this._schedule(this.fetchNext, 0);  // should never happen, but we never let the radio idle
        }
    };


    window.PychroniaMedia = {
        init: init,
        setI18n: setI18n,
        tryPlay: tryPlay,
        PersonalRadio: PersonalRadio,
        PublicRadio: PublicRadio
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            init();
        });
    } else {
        init();
    }

})(window, document);
