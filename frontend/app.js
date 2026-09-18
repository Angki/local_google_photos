// ==============================================================================
// File: frontend/app.js
// Description: Frontend application logic for Google Photos Local Gallery:
//              infinite scroll, timeline scrubber, AI semantic search,
//              lightbox viewer, and real-time WebSocket scanner tracking.
//
// CHANGELOG:
// 2026-09-05 - Initial creation: Implemented timeline rendering, debounced
//              semantic vector search, video streaming, interactive scrubber,
//              and resilient WebSocket client for background worker synchronization.
// ==============================================================================

(function () {
  "use strict";

  // State
  const state = {
    timeline: [],
    photos: [],
    currentCategory: "all",
    currentYear: null,
    currentMonth: null,
    searchQuery: "",
    offset: 0,
    limit: 60,
    hasMore: true,
    isLoading: false,
    lightboxIndex: -1,
    scannerStatus: null,
    ws: null,
    selectedPhotos: new Set(),
    lastSelectedId: null,
  };

  // DOM Elements
  const elements = {
    timelineSections: document.getElementById("timelineSections"),
    scrollSentinel: document.getElementById("scrollSentinel"),
    loadingSpinner: document.getElementById("loadingSpinner"),
    emptyState: document.getElementById("emptyState"),
    emptyTitle: document.getElementById("emptyTitle"),
    emptySubtext: document.getElementById("emptySubtext"),
    filterBanner: document.getElementById("filterBanner"),
    filterDesc: document.getElementById("filterDesc"),
    resetFilterBtn: document.getElementById("resetFilterBtn"),
    chipsWrapper: document.getElementById("chipsWrapper"),
    searchInput: document.getElementById("searchInput"),
    clearSearchBtn: document.getElementById("clearSearchBtn"),
    searchBadge: document.getElementById("searchBadge"),
    syncPill: document.getElementById("syncPill"),
    syncIndicator: document.getElementById("syncIndicator"),
    syncText: document.getElementById("syncText"),
    themeToggleBtn: document.getElementById("themeToggleBtn"),
    rescanBtn: document.getElementById("rescanBtn"),
    scrubberTrack: document.getElementById("scrubberTrack"),
    scrubberBubble: document.getElementById("scrubberBubble"),
    scrubberBubbleText: document.getElementById("scrubberBubbleText"),

    // Lightbox
    lightboxModal: document.getElementById("lightboxModal"),
    lightboxBackdrop: document.getElementById("lightboxBackdrop"),
    lightboxBackBtn: document.getElementById("lightboxBackBtn"),
    lightboxDate: document.getElementById("lightboxDate"),
    lightboxFilename: document.getElementById("lightboxFilename"),
    lightboxImg: document.getElementById("lightboxImg"),
    lightboxVideo: document.getElementById("lightboxVideo"),
    navPrevBtn: document.getElementById("navPrevBtn"),
    navNextBtn: document.getElementById("navNextBtn"),
    lightboxInfoToggleBtn: document.getElementById("lightboxInfoToggleBtn"),
    lightboxOpenOriginalBtn: document.getElementById("lightboxOpenOriginalBtn"),
    infoSidebar: document.getElementById("infoSidebar"),
    closeSidebarBtn: document.getElementById("closeSidebarBtn"),
    infoTaken: document.getElementById("infoTaken"),
    infoAiCategory: document.getElementById("infoAiCategory"),
    infoAiConf: document.getElementById("infoAiConf"),
    infoAiTags: document.getElementById("infoAiTags"),
    infoDimensions: document.getElementById("infoDimensions"),
    infoSize: document.getElementById("infoSize"),
    infoFolder: document.getElementById("infoFolder"),
    infoDevice: document.getElementById("infoDevice"),
    infoDescBlock: document.getElementById("infoDescBlock"),
    infoDescription: document.getElementById("infoDescription"),
    infoGeoBlock: document.getElementById("infoGeoBlock"),
    infoGeoCoords: document.getElementById("infoGeoCoords"),
    infoMapsLink: document.getElementById("infoMapsLink"),
    infoPeopleBlock: document.getElementById("infoPeopleBlock"),
    infoPeopleTags: document.getElementById("infoPeopleTags"),

    // Sync Modal
    syncModalWrapper: document.getElementById("syncModalWrapper"),
    syncModalBackdrop: document.getElementById("syncModalBackdrop"),
    syncModalCloseBtn: document.getElementById("syncModalCloseBtn"),
    syncModalTitle: document.getElementById("syncModalTitle"),
    syncModalStage: document.getElementById("syncModalStage"),
    syncProgressBar: document.getElementById("syncProgressBar"),
    syncPercentText: document.getElementById("syncPercentText"),
    syncSpeedText: document.getElementById("syncSpeedText"),
    metricDiscovered: document.getElementById("metricDiscovered"),
    metricIndexed: document.getElementById("metricIndexed"),
    metricThumbnails: document.getElementById("metricThumbnails"),
    metricAi: document.getElementById("metricAi"),
    syncCurrentFile: document.getElementById("syncCurrentFile"),
    syncPauseBtn: document.getElementById("syncPauseBtn"),
    syncResumeBtn: document.getElementById("syncResumeBtn"),
    syncRescanActionBtn: document.getElementById("syncRescanActionBtn"),

    // Selection & Albums
    selectionBar: document.getElementById("selectionBar"),
    selectionCount: document.getElementById("selectionCount"),
    cancelSelectionBtn: document.getElementById("cancelSelectionBtn"),
    selectAllVisibleBtn: document.getElementById("selectAllVisibleBtn"),
    addToAlbumBtn: document.getElementById("addToAlbumBtn"),
    deleteSelectedBtn: document.getElementById("deleteSelectedBtn"),
    albumModalWrapper: document.getElementById("albumModalWrapper"),
    albumModalBackdrop: document.getElementById("albumModalBackdrop"),
    albumModalCloseBtn: document.getElementById("albumModalCloseBtn"),
    newAlbumName: document.getElementById("newAlbumName"),
    createAlbumBtn: document.getElementById("createAlbumBtn"),
    albumList: document.getElementById("albumList"),
    lightboxDeleteBtn: document.getElementById("lightboxDeleteBtn"),
    toastContainer: document.getElementById("toastContainer"),

    // Delete Confirmation Modal (Option B)
    deleteModalWrapper: document.getElementById("deleteModalWrapper"),
    deleteModalBackdrop: document.getElementById("deleteModalBackdrop"),
    deleteModalCloseBtn: document.getElementById("deleteModalCloseBtn"),
    deleteModalCancelBtn: document.getElementById("deleteModalCancelBtn"),
    deleteModalConfirmBtn: document.getElementById("deleteModalConfirmBtn"),
    deleteModalTitle: document.getElementById("deleteModalTitle"),
    deleteModalMessage: document.getElementById("deleteModalMessage"),
    optSoft: document.getElementById("optSoft"),
    optHard: document.getElementById("optHard"),
    optSoftLabel: document.getElementById("optSoftLabel"),
    optHardLabel: document.getElementById("optHardLabel"),
    
    // Album View (Standalone)
    timelineContainer: document.getElementById("timelineContainer"),
    timelineScrubber: document.getElementById("timelineScrubber"),
    albumContainer: document.getElementById("albumContainer"),
    albumBackBtn: document.getElementById("albumBackBtn"),
    albumTitle: document.getElementById("albumTitle"),
    deleteAlbumBtn: document.getElementById("deleteAlbumBtn"),
    albumGrid: document.getElementById("albumGrid"),

    // Trash (Tempat Sampah) View
    trashChip: document.getElementById("trashChip"),
    trashBadgeCount: document.getElementById("trashBadgeCount"),
    trashContainer: document.getElementById("trashContainer"),
    trashBackBtn: document.getElementById("trashBackBtn"),
    trashCountBadge: document.getElementById("trashCountBadge"),
    emptyTrashBtn: document.getElementById("emptyTrashBtn"),
    trashGrid: document.getElementById("trashGrid"),
    trashEmptyState: document.getElementById("trashEmptyState"),
    restoreSelectedBtn: document.getElementById("restoreSelectedBtn"),
    permanentDeleteSelectedBtn: document.getElementById("permanentDeleteSelectedBtn"),
    lightboxRestoreBtn: document.getElementById("lightboxRestoreBtn"),
    lightboxPermanentDeleteBtn: document.getElementById("lightboxPermanentDeleteBtn"),
    emptyTrashModalWrapper: document.getElementById("emptyTrashModalWrapper"),
    emptyTrashModalBackdrop: document.getElementById("emptyTrashModalBackdrop"),
    emptyTrashModalCloseBtn: document.getElementById("emptyTrashModalCloseBtn"),
    emptyTrashModalCancelBtn: document.getElementById("emptyTrashModalCancelBtn"),
    emptyTrashModalConfirmBtn: document.getElementById("emptyTrashModalConfirmBtn"),

    // Photo Map View
    mapChip: document.getElementById("mapChip"),
    mapContainer: document.getElementById("mapContainer"),
    photoMapCanvas: document.getElementById("photoMapCanvas"),
    mapBackBtn: document.getElementById("mapBackBtn"),
    mapFitAllBtn: document.getElementById("mapFitAllBtn"),
    mapCountBadge: document.getElementById("mapCountBadge"),
    mapTraySheet: document.getElementById("mapTraySheet"),
    mapTrayHeader: document.getElementById("mapTrayHeader"),
    mapTrayGrid: document.getElementById("mapTrayGrid"),
    mapTrayCount: document.getElementById("mapTrayCount"),
    mapTrayToggleBtn: document.getElementById("mapTrayToggleBtn"),
    lightboxMiniMap: document.getElementById("lightboxMiniMap"),
    openInPhotoMapBtn: document.getElementById("openInPhotoMapBtn"),
  };

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------
  function init() {
    setupTheme();
    setupEventListeners();
    setupWebSocket();
    setupIntersectionObserver();
    setupScrollSpy();
    loadTimelineHierarchy();
    updateTrashBadge();
    fetchPhotos(true);
  }

  // --------------------------------------------------------------------------
  // Theme Toggle
  // --------------------------------------------------------------------------
  function setupTheme() {
    const saved = localStorage.getItem("gp_theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("gp_theme", next);
    updateMapTilesTheme();
  }

  // --------------------------------------------------------------------------
  // WebSocket Status Tracking & HTTP Polling Fallback
  // --------------------------------------------------------------------------
  let wsFailCount = 0;
  let pollingInterval = null;

  function pollStatusHttp() {
    fetch("/ws/status")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) handleStatusUpdate(data);
      })
      .catch(() => {});
  }

  function startPollingFallback() {
    if (!pollingInterval) {
      pollStatusHttp();
      pollingInterval = setInterval(pollStatusHttp, 3000);
    }
  }

  function setupWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/status`;

    try {
      state.ws = new WebSocket(wsUrl);
    } catch (e) {
      startPollingFallback();
      return;
    }

    state.ws.onopen = () => {
      wsFailCount = 0;
      if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }
    };

    state.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleStatusUpdate(data);
      } catch (e) {
        console.error("WS Parse error", e);
      }
    };

    state.ws.onerror = () => {
      wsFailCount++;
      if (wsFailCount >= 2 && !pollingInterval) {
        startPollingFallback();
      }
    };

    state.ws.onclose = () => {
      wsFailCount++;
      if (wsFailCount >= 2) {
        startPollingFallback();
        // Exponential backoff up to 30s
        const delay = Math.min(30000, 3000 * Math.pow(1.5, wsFailCount - 2));
        setTimeout(setupWebSocket, delay);
      } else {
        setTimeout(setupWebSocket, 3000);
      }
    };
  }

  function handleStatusUpdate(status) {
    state.scannerStatus = status;

    // Update Header Sync Pill
    const isScanning = status.status === "scanning_metadata" || status.status === "processing_media";
    const isPaused = status.status === "paused";

    elements.syncIndicator.className = "sync-indicator" + (isScanning ? " syncing" : isPaused ? " paused" : "");

    if (isScanning) {
      elements.syncText.textContent = `Syncing ${status.percent}% (${status.metadata_indexed.toLocaleString()}/${status.total_discovered.toLocaleString()})`;
    } else if (isPaused) {
      elements.syncText.textContent = `Paused (${status.percent}%)`;
    } else if (status.status === "completed") {
      elements.syncText.textContent = `Library Ready (${status.metadata_indexed.toLocaleString()} items)`;
    } else {
      elements.syncText.textContent = `${status.metadata_indexed.toLocaleString()} items`;
    }

    // Update Modal elements if visible
    if (!elements.syncModalWrapper.classList.contains("hidden")) {
      renderSyncModal(status);
    }
  }

  function renderSyncModal(status) {
    elements.syncProgressBar.style.width = `${status.percent}%`;
    elements.syncPercentText.textContent = `${status.percent}% Complete`;
    elements.syncSpeedText.textContent = `${status.speed_fps} items/sec`;
    elements.metricDiscovered.textContent = (status.total_discovered || 0).toLocaleString();
    elements.metricIndexed.textContent = (status.metadata_indexed || 0).toLocaleString();
    elements.metricThumbnails.textContent = (status.thumbnails_done || 0).toLocaleString();
    elements.metricAi.textContent = (status.ai_processed || 0).toLocaleString();
    elements.syncCurrentFile.textContent = status.current_file || "Ready";

    if (status.status === "scanning_metadata") {
      elements.syncModalTitle.textContent = "Stage 1: Ingesting Metadata";
      elements.syncModalStage.textContent = `Reading Google Takeout JSON files in ${status.current_folder}...`;
      elements.syncPauseBtn.style.display = "inline-block";
      elements.syncResumeBtn.style.display = "none";
    } else if (status.status === "processing_media") {
      elements.syncModalTitle.textContent = "Stage 2: Thumbnails & AI CLIP";
      elements.syncModalStage.textContent = "Generating fast WebP thumbnails & zero-shot categorization...";
      elements.syncPauseBtn.style.display = "inline-block";
      elements.syncResumeBtn.style.display = "none";
    } else if (status.status === "paused") {
      elements.syncModalTitle.textContent = "Scanning Paused";
      elements.syncModalStage.textContent = "Background indexing is currently paused.";
      elements.syncPauseBtn.style.display = "none";
      elements.syncResumeBtn.style.display = "inline-block";
    } else {
      elements.syncModalTitle.textContent = "Archive Fully Synced";
      elements.syncModalStage.textContent = "All Google Takeout files are indexed.";
      elements.syncPauseBtn.style.display = "none";
      elements.syncResumeBtn.style.display = "none";
    }
  }

  // --------------------------------------------------------------------------
  // Timeline Scrubber & Hierarchy (Year + Month Rail)
  // --------------------------------------------------------------------------
  const shortMonthNames = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
  };

  const fullMonthNames = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
  };

  async function loadTimelineHierarchy() {
    try {
      const res = await fetch("/api/timeline");
      const data = await res.json();
      state.timeline = data.timeline || [];
      renderScrubber(state.timeline);
    } catch (e) {
      console.error("Failed to load timeline hierarchy", e);
    }
  }

  function renderScrubber(timeline) {
    elements.scrubberTrack.innerHTML = "";
    if (!timeline || timeline.length === 0) return;

    timeline.forEach((item, index) => {
      const yearGroup = document.createElement("div");
      yearGroup.className = "scrubber-year-group";
      yearGroup.setAttribute("data-year", item.year);

      // Year Header (Accordion toggle)
      const yearHeader = document.createElement("div");
      yearHeader.className = "scrubber-year-header" + (index === 0 ? " expanded" : "");

      const yearLabel = document.createElement("span");
      yearLabel.className = "scrubber-year-label";
      yearLabel.textContent = item.year;

      const chevron = document.createElement("span");
      chevron.className = "scrubber-year-chevron";
      chevron.innerHTML = `<svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

      yearHeader.appendChild(yearLabel);
      if (item.months && item.months.length > 0) {
        yearHeader.appendChild(chevron);
      }
      yearGroup.appendChild(yearHeader);

      // Months list
      let monthsList = null;
      if (item.months && item.months.length > 0) {
        monthsList = document.createElement("div");
        monthsList.className = "scrubber-months-list" + (index === 0 ? " open" : "");

        item.months.forEach((m) => {
          const mNode = document.createElement("div");
          mNode.className = "scrubber-month-node";
          mNode.setAttribute("data-year", item.year);
          mNode.setAttribute("data-month", m.month);

          const mShort = shortMonthNames[m.month] || m.month_name.slice(0, 3);
          const mFull = fullMonthNames[m.month] || m.month_name;

          mNode.textContent = mShort;

          mNode.addEventListener("click", (e) => {
            e.stopPropagation();
            scrollToMonth(item.year, m.month, mFull);
          });

          mNode.addEventListener("mouseenter", () => {
            showScrubberBubble(mNode, `📅 ${mFull} ${item.year} • ${m.count.toLocaleString()} foto`);
          });

          mNode.addEventListener("mouseleave", () => {
            hideScrubberBubble();
          });

          monthsList.appendChild(mNode);
        });

        yearGroup.appendChild(monthsList);
      }

      // Year Header Click
      yearHeader.addEventListener("click", (e) => {
        e.stopPropagation();
        if (monthsList) {
          const wasOpen = monthsList.classList.contains("open");
          monthsList.classList.toggle("open", !wasOpen);
          yearHeader.classList.toggle("expanded", !wasOpen);
        }
        scrollToYear(item.year);
      });

      yearHeader.addEventListener("mouseenter", () => {
        showScrubberBubble(yearHeader, `📅 ${item.year} • ${item.total.toLocaleString()} foto`);
      });

      yearHeader.addEventListener("mouseleave", () => {
        hideScrubberBubble();
      });

      elements.scrubberTrack.appendChild(yearGroup);
    });

    // Update active highlight based on current scroll position
    updateActiveScrubberNode();
  }

  function showScrubberBubble(targetEl, text) {
    if (!elements.scrubberBubble || !elements.scrubberBubbleText) return;
    elements.scrubberBubbleText.textContent = text;
    elements.scrubberBubble.classList.remove("hidden");

    const rect = targetEl.getBoundingClientRect();
    const bubbleRect = elements.scrubberBubble.getBoundingClientRect();
    const topPos = rect.top + (rect.height / 2) - (bubbleRect.height / 2);
    elements.scrubberBubble.style.top = `${Math.max(10, topPos)}px`;
  }

  function hideScrubberBubble() {
    if (elements.scrubberBubble) {
      elements.scrubberBubble.classList.add("hidden");
    }
  }

  function setupScrollSpy() {
    let ticking = false;
    window.addEventListener(
      "scroll",
      () => {
        if (!ticking) {
          window.requestAnimationFrame(() => {
            updateActiveScrubberNode();
            ticking = false;
          });
          ticking = true;
        }
      },
      { passive: true }
    );
  }

  function updateActiveScrubberNode() {
    const sections = document.querySelectorAll(".timeline-section");
    if (!sections || sections.length === 0) return;

    let currentSection = null;
    const headerOffset = 150;

    for (let i = 0; i < sections.length; i++) {
      const rect = sections[i].getBoundingClientRect();
      if (rect.top <= headerOffset && rect.bottom > headerOffset) {
        currentSection = sections[i];
        break;
      }
      if (rect.top > headerOffset) {
        if (!currentSection) currentSection = sections[i];
        break;
      }
    }

    if (!currentSection && sections.length > 0) {
      currentSection = sections[sections.length - 1];
    }

    if (currentSection) {
      const year = currentSection.getAttribute("data-section-year");
      const key = currentSection.getAttribute("data-section-key"); // e.g. "2026-8"

      document.querySelectorAll(".scrubber-year-header.active, .scrubber-month-node.active").forEach((el) => {
        el.classList.remove("active");
      });

      const activeYearGroup = document.querySelector(`.scrubber-year-group[data-year="${year}"]`);
      if (activeYearGroup) {
        const header = activeYearGroup.querySelector(".scrubber-year-header");
        if (header) header.classList.add("active");

        if (key) {
          const parts = key.split("-");
          if (parts.length === 2) {
            const m = parts[1];
            const mNode = activeYearGroup.querySelector(`.scrubber-month-node[data-month="${m}"]`);
            if (mNode) mNode.classList.add("active");
          }
        }
      }
    }
  }

  async function scrollToYear(year) {
    state.currentMonth = null;
    const targetSection = document.querySelector(`[data-section-year="${year}"]`);
    if (targetSection && !state.searchQuery && state.currentCategory === "all") {
      targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    // Jump directly to that year!
    state.lastSelectedId = null;
    state.currentYear = year;
    state.currentMonth = null;
    state.searchQuery = "";
    elements.searchInput.value = "";
    elements.clearSearchBtn.classList.add("hidden");
    elements.filterBanner.classList.remove("hidden");
    elements.filterDesc.textContent = `Showing photos from ${year}`;

    await fetchPhotos(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function scrollToMonth(year, month, monthName) {
    const targetKey = `${year}-${month}`;
    const targetSection = document.querySelector(`[data-section-key="${targetKey}"]`);
    if (targetSection && !state.searchQuery && state.currentCategory === "all" && !state.currentMonth) {
      targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    // Jump directly to that specific month & year!
    state.lastSelectedId = null;
    state.currentYear = year;
    state.currentMonth = month;
    state.searchQuery = "";
    elements.searchInput.value = "";
    elements.clearSearchBtn.classList.add("hidden");
    elements.filterBanner.classList.remove("hidden");
    elements.filterDesc.textContent = `Showing photos from ${monthName || `Month ${month}`} ${year}`;

    await fetchPhotos(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // --------------------------------------------------------------------------
  // Fetch Photos & Infinite Scroll
  // --------------------------------------------------------------------------
  async function fetchPhotos(reset = false) {
    if (state.isLoading) return;
    if (!reset && !state.hasMore) return;

    state.isLoading = true;
    elements.loadingSpinner.classList.remove("hidden");

    if (reset) {
      state.offset = 0;
      state.photos = [];
      state.hasMore = true;
      elements.timelineSections.innerHTML = "";
    }

    try {
      let url = "";
      if (state.searchQuery) {
        url = `/api/search?q=${encodeURIComponent(state.searchQuery)}&limit=${state.limit}`;
        elements.filterBanner.classList.remove("hidden");
        elements.filterDesc.textContent = `Search results for "${state.searchQuery}"`;
      } else {
        const params = new URLSearchParams({
          limit: state.limit,
          offset: state.offset,
        });
        if (state.currentYear) {
          params.append("year", state.currentYear);
        }
        if (state.currentMonth) {
          params.append("month", state.currentMonth);
        }
        if (state.currentCategory !== "all") {
          if (state.currentCategory === "videos") {
            params.append("media_type", "video");
          } else {
            params.append("category", state.currentCategory);
          }
        }
        url = `/api/photos?${params.toString()}`;

        if (state.currentCategory !== "all") {
          elements.filterBanner.classList.remove("hidden");
          elements.filterDesc.textContent = `Showing ${state.currentCategory.toUpperCase()}`;
        } else if (state.currentYear && state.currentMonth) {
          const mName = fullMonthNames[state.currentMonth] || `Month ${state.currentMonth}`;
          elements.filterBanner.classList.remove("hidden");
          elements.filterDesc.textContent = `Showing photos from ${mName} ${state.currentYear}`;
        } else if (state.currentYear) {
          elements.filterBanner.classList.remove("hidden");
          elements.filterDesc.textContent = `Showing photos from ${state.currentYear}`;
        } else {
          elements.filterBanner.classList.add("hidden");
        }
      }

      const res = await fetch(url);
      const data = await res.json();
      const newPhotos = data.photos || [];

      if (data.mode === "semantic") {
        elements.searchBadge.innerHTML = `<span class="sparkle-icon">✨</span> AI Match`;
      } else {
        elements.searchBadge.innerHTML = `<span class="sparkle-icon">✨</span> AI Search`;
      }

      if (reset) {
        state.photos = newPhotos;
      } else {
        state.photos.push(...newPhotos);
      }

      if (state.searchQuery || newPhotos.length < state.limit) {
        state.hasMore = false;
      } else {
        state.offset += newPhotos.length;
      }

      renderGallery(reset, newPhotos);
    } catch (e) {
      console.error("Error fetching photos", e);
    } finally {
      state.isLoading = false;
      elements.loadingSpinner.classList.add("hidden");
    }
  }

  function renderGallery(reset = false, newItems = []) {
    if (state.photos.length === 0) {
      elements.emptyState.classList.remove("hidden");
      elements.timelineSections.innerHTML = "";
      return;
    }

    elements.emptyState.classList.add("hidden");

    if (reset) {
      elements.timelineSections.innerHTML = "";
      const groups = groupPhotosByMonth(state.photos);
      groups.forEach((group) => {
        elements.timelineSections.appendChild(createSectionElement(group));
      });
    } else {
      // Incremental render without clearing existing DOM!
      const itemsToAppend = newItems.length > 0 ? newItems : state.photos;
      const newGroups = groupPhotosByMonth(itemsToAppend);

      newGroups.forEach((group) => {
        let section = elements.timelineSections.querySelector(`[data-section-key="${group.key}"]`);
        if (section) {
          const grid = section.querySelector(".photo-grid");
          const countEl = section.querySelector(".timeline-count");
          group.photos.forEach((photo) => {
            grid.appendChild(createPhotoTile(photo));
          });
          const totalInGrid = grid.querySelectorAll(".photo-tile").length;
          if (countEl) {
            countEl.textContent = `${totalInGrid} item${totalInGrid > 1 ? "s" : ""}`;
          }
        } else {
          elements.timelineSections.appendChild(createSectionElement(group));
        }
      });
    }
  }

  function createSectionElement(group) {
    const section = document.createElement("section");
    section.className = "timeline-section";
    section.setAttribute("data-section-year", group.year);
    section.setAttribute("data-section-key", group.key);

    const header = document.createElement("div");
    header.className = "timeline-header";

    const title = document.createElement("h2");
    title.className = "timeline-title";
    title.textContent = `${group.monthName} ${group.year}`;

    const count = document.createElement("span");
    count.className = "timeline-count";
    count.textContent = `${group.photos.length} item${group.photos.length > 1 ? "s" : ""}`;

    header.appendChild(title);
    header.appendChild(count);
    section.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "photo-grid";

    group.photos.forEach((photo) => {
      const tile = createPhotoTile(photo);
      grid.appendChild(tile);
    });

    section.appendChild(grid);
    return section;
  }

  function groupPhotosByMonth(photosList) {
    const monthNames = [
      "", "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];

    const map = new Map();
    photosList.forEach((photo) => {
      const y = photo.taken_year || 2026;
      const m = photo.taken_month || 1;
      const key = `${y}-${m}`;

      if (!map.has(key)) {
        map.set(key, {
          key,
          year: y,
          month: m,
          monthName: monthNames[m] || `Month ${m}`,
          photos: [],
        });
      }
      map.get(key).photos.push(photo);
    });

    return Array.from(map.values());
  }

  function createPhotoTile(photo) {
    const tile = document.createElement("div");
    tile.className = "photo-tile";
    tile.setAttribute("data-id", photo.id);

    const img = document.createElement("img");
    img.className = "photo-thumb loading";
    img.alt = photo.description || photo.filename;
    img.loading = "lazy";

    // Set thumbnail URL
    img.src = `/api/thumbnails/${photo.id}`;
    img.onload = () => {
      img.classList.remove("loading");
      img.classList.add("loaded");
    };
    img.onerror = () => {
      if (!img.dataset.fallbackTried) {
        img.dataset.fallbackTried = "true";
        img.src = `/api/media/${photo.id}`; // Fallback once to original
      } else {
        img.onerror = null; // Unbind immediately to prevent loops
        img.classList.remove("loading");
        img.classList.add("loaded");
        img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='1.5'%3E%3Crect x='3' y='3' width='18' height='18' rx='2' ry='2'/%3E%3Ccircle cx='8.5' r='1.5'/%3E%3Cpolyline points='21 15 16 10 5 21'/%3E%3C/svg%3E";
      }
    };

    tile.appendChild(img);

    // Video duration/play badge
    if (photo.media_type === "video") {
      const vidBadge = document.createElement("div");
      vidBadge.className = "video-badge";
      vidBadge.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> VIDEO`;
      tile.appendChild(vidBadge);
    }

    // AI Tag badge on hover
    if (photo.ai_category) {
      const tagBadge = document.createElement("div");
      tagBadge.className = "category-tag-badge";
      tagBadge.textContent = photo.ai_category;
      tile.appendChild(tagBadge);
    }

    // Geolocation GPS pin badge
    if (photo.has_geo) {
      const geoBadge = document.createElement("div");
      geoBadge.className = "geo-badge";
      geoBadge.title = "Ada data lokasi (GPS)";
      geoBadge.innerHTML = `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`;
      tile.appendChild(geoBadge);
    }

    // Selection Overlay Checkmark Circle (Google Photos style)
    const selectOverlay = document.createElement("div");
    selectOverlay.className = "select-overlay";
    selectOverlay.title = "Select photo";
    selectOverlay.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      handlePhotoSelection(photo.id, tile, e.shiftKey);
    });
    tile.appendChild(selectOverlay);

    if (state.selectedPhotos.has(photo.id)) {
      tile.classList.add("selected");
    }

    tile.addEventListener("click", (e) => {
      if (state.selectedPhotos.size > 0 || e.shiftKey) {
        handlePhotoSelection(photo.id, tile, e.shiftKey);
      } else {
        openLightbox(photo.id);
      }
    });

    return tile;
  }

  function setupIntersectionObserver() {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !state.isLoading && state.hasMore) {
          fetchPhotos(false);
        }
      },
      { rootMargin: "600px" }
    );
    observer.observe(elements.scrollSentinel);
  }

  // --------------------------------------------------------------------------
  // Fullscreen Lightbox & Info Pane
  // --------------------------------------------------------------------------
  async function openLightbox(photoId) {
    state.lightboxIndex = state.photos.findIndex((p) => p.id === photoId);
    if (state.lightboxIndex === -1) {
      // Look in geoPointsCache first or fetch
      let photoObj = geoPointsCache ? geoPointsCache.find((p) => p.id === photoId) : null;
      if (!photoObj) {
        try {
          const res = await fetch(`/api/photos/${photoId}`);
          if (res.ok) {
            photoObj = await res.json();
          }
        } catch (e) {
          console.error("Error fetching photo for lightbox", e);
        }
      }
      if (photoObj) {
        state.photos.push(photoObj);
        state.lightboxIndex = state.photos.length - 1;
      } else {
        return;
      }
    }

    renderLightboxPhoto();
    elements.lightboxModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  window.__openPhotoById = openLightbox;

  function closeLightbox() {
    elements.lightboxModal.classList.add("hidden");
    elements.lightboxVideo.pause();
    elements.lightboxVideo.src = "";
    elements.infoSidebar.classList.remove("open");
    document.body.style.overflow = "";
  }

  function navigateLightbox(step) {
    const newIdx = state.lightboxIndex + step;
    if (newIdx >= 0 && newIdx < state.photos.length) {
      state.lightboxIndex = newIdx;
      renderLightboxPhoto();
    }
  }

  function renderLightboxPhoto() {
    const photo = state.photos[state.lightboxIndex];
    if (!photo) return;

    elements.lightboxDate.textContent = photo.taken_formatted || "Unknown Date";
    elements.lightboxFilename.textContent = photo.filename;

    if (photo.media_type === "video") {
      elements.lightboxImg.classList.add("hidden");
      elements.lightboxVideo.classList.remove("hidden");
      elements.lightboxVideo.src = `/api/media/${photo.id}`;
      elements.lightboxVideo.play().catch(() => {});
    } else {
      elements.lightboxVideo.classList.add("hidden");
      elements.lightboxVideo.pause();
      elements.lightboxVideo.src = "";
      elements.lightboxImg.classList.remove("hidden");
      elements.lightboxImg.src = `/api/media/${photo.id}`;
    }

    // Populate Sidebar Details
    elements.infoTaken.textContent = photo.taken_formatted || "Unknown";
    elements.infoAiCategory.textContent = photo.ai_category || "Unclassified";
    elements.infoAiConf.textContent = photo.ai_confidence ? `${Math.round(photo.ai_confidence * 100)}% match` : "";

    // AI Tags
    elements.infoAiTags.innerHTML = "";
    if (photo.ai_tags && photo.ai_tags.length) {
      photo.ai_tags.forEach((tag) => {
        const item = document.createElement("span");
        item.className = "tag-item";
        item.textContent = `#${tag}`;
        elements.infoAiTags.appendChild(item);
      });
    }

    elements.infoDimensions.textContent = photo.width && photo.height ? `${photo.width} × ${photo.height}` : "Unknown";
    elements.infoSize.textContent = formatBytes(photo.file_size);
    elements.infoFolder.textContent = photo.folder_year || "--";
    elements.infoDevice.textContent = photo.device_folder || "Local Storage";

    // Description
    if (photo.description) {
      elements.infoDescBlock.classList.remove("hidden");
      elements.infoDescription.textContent = photo.description;
    } else {
      elements.infoDescBlock.classList.add("hidden");
    }

    // Geolocation
    if (photo.has_geo && photo.latitude && photo.longitude) {
      elements.infoGeoBlock.classList.remove("hidden");
      elements.infoGeoCoords.textContent = `${photo.latitude.toFixed(5)}, ${photo.longitude.toFixed(5)}`;
      elements.infoMapsLink.href = `https://www.google.com/maps?q=${photo.latitude},${photo.longitude}`;
      updateLightboxMiniMap(photo.latitude, photo.longitude);
    } else {
      elements.infoGeoBlock.classList.add("hidden");
    }

    // People
    if (photo.people && photo.people.length) {
      elements.infoPeopleBlock.classList.remove("hidden");
      elements.infoPeopleTags.innerHTML = "";
      photo.people.forEach((person) => {
        const item = document.createElement("span");
        item.className = "tag-item";
        item.textContent = person;
        elements.infoPeopleTags.appendChild(item);
      });
    } else {
      elements.infoPeopleBlock.classList.add("hidden");
    }

    elements.lightboxOpenOriginalBtn.onclick = () => {
      window.open(`/api/media/${photo.id}`, "_blank");
    };

    // Toggle actions for Trash view vs Regular gallery
    if (state.currentCategory === "trash") {
      if (elements.lightboxDeleteBtn) elements.lightboxDeleteBtn.style.display = "none";
      if (elements.lightboxRestoreBtn) elements.lightboxRestoreBtn.style.display = "inline-flex";
      if (elements.lightboxPermanentDeleteBtn) elements.lightboxPermanentDeleteBtn.style.display = "inline-flex";
    } else {
      if (elements.lightboxDeleteBtn) elements.lightboxDeleteBtn.style.display = "inline-flex";
      if (elements.lightboxRestoreBtn) elements.lightboxRestoreBtn.style.display = "none";
      if (elements.lightboxPermanentDeleteBtn) elements.lightboxPermanentDeleteBtn.style.display = "none";
    }
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  // --------------------------------------------------------------------------
  // Event Listeners
  // --------------------------------------------------------------------------
  function setupEventListeners() {
    // Theme toggle
    elements.themeToggleBtn.addEventListener("click", toggleTheme);

    // Sync Pill opens modal
    elements.syncPill.addEventListener("click", () => {
      elements.syncModalWrapper.classList.remove("hidden");
      if (state.scannerStatus) renderSyncModal(state.scannerStatus);
    });

    elements.syncModalCloseBtn.addEventListener("click", () => {
      elements.syncModalWrapper.classList.add("hidden");
    });
    elements.syncModalBackdrop.addEventListener("click", () => {
      elements.syncModalWrapper.classList.add("hidden");
    });

    // Scanner Controls
    elements.syncPauseBtn.addEventListener("click", () => {
      fetch("/api/scan/pause", { method: "POST" });
    });
    elements.syncResumeBtn.addEventListener("click", () => {
      fetch("/api/scan/resume", { method: "POST" });
    });
    elements.syncRescanActionBtn.addEventListener("click", () => {
      if (confirm("Force re-scan and re-evaluate all Takeout photos from 2013-2026?")) {
        fetch("/api/scan/start", { method: "POST" });
      }
    });

    elements.rescanBtn.addEventListener("click", () => {
      elements.syncModalWrapper.classList.remove("hidden");
      fetch("/api/scan/start", { method: "POST" });
    });

    // Search Input Debounce
    let searchTimer = null;
    elements.searchInput.addEventListener("input", (e) => {
      const val = e.target.value.trim();
      elements.clearSearchBtn.classList.toggle("hidden", !val);

      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        state.searchQuery = val;
        fetchPhotos(true);
      }, 350);
    });

    elements.clearSearchBtn.addEventListener("click", () => {
      elements.searchInput.value = "";
      elements.clearSearchBtn.classList.add("hidden");
      state.searchQuery = "";
      fetchPhotos(true);
    });

    // Reset filter banner
    elements.resetFilterBtn.addEventListener("click", () => {
      elements.searchInput.value = "";
      elements.clearSearchBtn.classList.add("hidden");
      state.searchQuery = "";
      state.currentCategory = "all";
      state.currentYear = null;
      state.currentMonth = null;
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      document.querySelector('[data-category="all"]').classList.add("active");
      fetchPhotos(true);
    });

    // Category chips
    elements.chipsWrapper.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;

      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");

      state.currentCategory = chip.dataset.category;
      state.currentYear = null;
      state.currentMonth = null;
      
      if (state.currentCategory === "trash") {
        hideAlbumView();
        hidePhotoMapView();
        showTrashView();
      } else if (state.currentCategory === "albums") {
        hideTrashView();
        hidePhotoMapView();
        showAlbumList();
      } else if (state.currentCategory === "map") {
        hideTrashView();
        hideAlbumView();
        showPhotoMapView();
      } else {
        hideTrashView();
        hideAlbumView();
        hidePhotoMapView();
        fetchPhotos(true);
      }
    });

    // Lightbox events
    elements.lightboxBackBtn.addEventListener("click", closeLightbox);
    elements.lightboxBackdrop.addEventListener("click", closeLightbox);
    elements.navPrevBtn.addEventListener("click", () => navigateLightbox(-1));
    elements.navNextBtn.addEventListener("click", () => navigateLightbox(1));

    elements.lightboxInfoToggleBtn.addEventListener("click", () => {
      elements.infoSidebar.classList.toggle("open");
    });
    elements.closeSidebarBtn.addEventListener("click", () => {
      elements.infoSidebar.classList.remove("open");
    });

    // Keyboard navigation
    window.addEventListener("keydown", (e) => {
      if (!elements.lightboxModal.classList.contains("hidden")) {
        if (e.key === "Escape") closeLightbox();
        else if (e.key === "ArrowLeft") navigateLightbox(-1);
        else if (e.key === "ArrowRight") navigateLightbox(1);
        else if (e.key === "Delete" || e.key === "Backspace") {
          deleteCurrentLightboxPhoto();
        } else if (e.key.toLowerCase() === "i") {
          elements.infoSidebar.classList.toggle("open");
        }
      } else if (state.selectedPhotos.size > 0 && e.key === "Escape") {
        clearSelection();
      }
    });

    // --- Selection & Album Events ---
    elements.cancelSelectionBtn.addEventListener("click", clearSelection);
    if (elements.selectAllVisibleBtn) {
      elements.selectAllVisibleBtn.addEventListener("click", selectAllVisiblePhotos);
    }
    elements.deleteSelectedBtn.addEventListener("click", deleteSelectedPhotos);
    if (elements.lightboxDeleteBtn) {
      elements.lightboxDeleteBtn.addEventListener("click", deleteCurrentLightboxPhoto);
    }
    
    elements.addToAlbumBtn.addEventListener("click", () => {
      const count = state.selectedPhotos.size;
      if (elements.albumModalTitle) {
        elements.albumModalTitle.textContent = count > 0 ? `Tambahkan ke Album (${count} dipilih)` : "Add to Album";
      }
      elements.newAlbumName.value = "";
      elements.albumModalWrapper.classList.remove("hidden");
      setTimeout(() => elements.newAlbumName.focus(), 60);
      fetchAlbums();
    });
    elements.albumModalCloseBtn.addEventListener("click", () => {
      elements.albumModalWrapper.classList.add("hidden");
    });
    elements.albumModalBackdrop.addEventListener("click", () => {
      elements.albumModalWrapper.classList.add("hidden");
    });
    
    elements.createAlbumBtn.addEventListener("click", createAlbum);
    elements.newAlbumName.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        createAlbum();
      }
    });
    setupDeleteModalEvents();

    // --- Trash View Events ---
    if (elements.trashBackBtn) {
      elements.trashBackBtn.addEventListener("click", () => {
        document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        const allChip = document.querySelector('[data-category="all"]');
        if (allChip) allChip.classList.add("active");
        state.currentCategory = "all";
        hideTrashView();
        fetchPhotos(true);
      });
    }

    if (elements.emptyTrashBtn) {
      elements.emptyTrashBtn.addEventListener("click", openEmptyTrashModal);
    }
    if (elements.emptyTrashModalCloseBtn) {
      elements.emptyTrashModalCloseBtn.addEventListener("click", closeEmptyTrashModal);
    }
    if (elements.emptyTrashModalCancelBtn) {
      elements.emptyTrashModalCancelBtn.addEventListener("click", closeEmptyTrashModal);
    }
    if (elements.emptyTrashModalBackdrop) {
      elements.emptyTrashModalBackdrop.addEventListener("click", closeEmptyTrashModal);
    }
    if (elements.emptyTrashModalConfirmBtn) {
      elements.emptyTrashModalConfirmBtn.addEventListener("click", confirmEmptyTrash);
    }

    if (elements.restoreSelectedBtn) {
      elements.restoreSelectedBtn.addEventListener("click", restoreSelectedPhotos);
    }
    if (elements.permanentDeleteSelectedBtn) {
      elements.permanentDeleteSelectedBtn.addEventListener("click", permanentDeleteSelectedPhotos);
    }

    if (elements.lightboxRestoreBtn) {
      elements.lightboxRestoreBtn.addEventListener("click", restoreLightboxPhoto);
    }
    if (elements.lightboxPermanentDeleteBtn) {
      elements.lightboxPermanentDeleteBtn.addEventListener("click", permanentDeleteLightboxPhoto);
    }

    // --- Photo Map View Events ---
    if (elements.mapBackBtn) {
      elements.mapBackBtn.addEventListener("click", () => {
        hidePhotoMapView();
        state.currentCategory = "all";
        document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        const allChip = document.querySelector('[data-category="all"]');
        if (allChip) allChip.classList.add("active");
        elements.timelineContainer.classList.remove("hidden");
        elements.timelineScrubber.classList.remove("hidden");
        fetchPhotos(true);
      });
    }

    if (elements.mapFitAllBtn) {
      elements.mapFitAllBtn.addEventListener("click", () => {
        if (photoMapInstance && photoMapClusterGroup && photoMapClusterGroup.getLayers().length > 0) {
          photoMapInstance.fitBounds(photoMapClusterGroup.getBounds().pad(0.08));
        }
      });
    }

    if (elements.mapTrayHeader) {
      elements.mapTrayHeader.addEventListener("click", () => {
        elements.mapTraySheet.classList.toggle("collapsed");
      });
    }

    if (elements.openInPhotoMapBtn) {
      elements.openInPhotoMapBtn.addEventListener("click", () => {
        const photo = state.photos[state.lightboxIndex];
        if (!photo || !photo.latitude || !photo.longitude) return;
        const lat = photo.latitude;
        const lng = photo.longitude;
        const pid = photo.id;
        closeLightbox();
        hideTrashView();
        hideAlbumView();
        showPhotoMapView([lat, lng], 16, pid);
      });
    }
  }

  // --- Selection Logic ---

  function handlePhotoSelection(id, tileElement, isShift) {
    if (isShift && state.lastSelectedId && state.lastSelectedId !== id) {
      // Fast single-pass range search
      const allTiles = document.querySelectorAll(".photo-tile");
      let startIndex = -1;
      let endIndex = -1;
      for (let i = 0; i < allTiles.length; i++) {
        const tId = parseInt(allTiles[i].dataset.id);
        if (tId === state.lastSelectedId) startIndex = i;
        if (tId === id) endIndex = i;
        if (startIndex !== -1 && endIndex !== -1) break;
      }

      if (startIndex !== -1 && endIndex !== -1) {
        const start = Math.min(startIndex, endIndex);
        const end = Math.max(startIndex, endIndex);
        const cappedEnd = Math.min(end, start + 300);
        
        // Select all in range
        for (let i = start; i <= cappedEnd; i++) {
          const tId = parseInt(allTiles[i].dataset.id);
          if (tId) {
            state.selectedPhotos.add(tId);
            allTiles[i].classList.add("selected");
          }
        }
      }
    } else {
      // Toggle single
      if (state.selectedPhotos.has(id)) {
        state.selectedPhotos.delete(id);
        tileElement.classList.remove("selected");
      } else {
        state.selectedPhotos.add(id);
        tileElement.classList.add("selected");
      }
    }

    state.lastSelectedId = id;
    updateSelectionBar();
  }

  function selectAllVisiblePhotos() {
    const allTiles = document.querySelectorAll(".photo-tile");
    allTiles.forEach((tile) => {
      const id = parseInt(tile.dataset.id);
      if (id) {
        state.selectedPhotos.add(id);
        tile.classList.add("selected");
      }
    });
    updateSelectionBar();
  }

  function clearSelection() {
    state.selectedPhotos.clear();
    state.lastSelectedId = null;
    document.querySelectorAll(".photo-tile.selected").forEach(t => t.classList.remove("selected"));
    updateSelectionBar();
  }

  function updateSelectionBar() {
    const count = state.selectedPhotos.size;
    const isTrash = state.currentCategory === "trash";

    if (count > 0) {
      elements.selectionCount.textContent = `${count} selected`;
      elements.selectionBar.classList.remove("hidden");
      document.body.classList.add("is-selecting");

      if (isTrash) {
        if (elements.addToAlbumBtn) elements.addToAlbumBtn.classList.add("hidden");
        if (elements.deleteSelectedBtn) elements.deleteSelectedBtn.classList.add("hidden");
        if (elements.restoreSelectedBtn) elements.restoreSelectedBtn.classList.remove("hidden");
        if (elements.permanentDeleteSelectedBtn) elements.permanentDeleteSelectedBtn.classList.remove("hidden");
      } else {
        if (elements.addToAlbumBtn) elements.addToAlbumBtn.classList.remove("hidden");
        if (elements.deleteSelectedBtn) elements.deleteSelectedBtn.classList.remove("hidden");
        if (elements.restoreSelectedBtn) elements.restoreSelectedBtn.classList.add("hidden");
        if (elements.permanentDeleteSelectedBtn) elements.permanentDeleteSelectedBtn.classList.add("hidden");
      }
    } else {
      elements.selectionBar.classList.add("hidden");
      document.body.classList.remove("is-selecting");
    }
  }

  // --------------------------------------------------------------------------
  // Delete & Trash Actions
  // --------------------------------------------------------------------------

  async function deleteSelectedPhotos() {
    if (state.selectedPhotos.size === 0) return;
    const ids = Array.from(state.selectedPhotos);
    const count = ids.length;

    // If already in Trash view, route to permanent delete:
    if (state.currentCategory === "trash") {
      permanentDeleteSelectedPhotos();
      return;
    }

    // Default gallery: Move to Trash immediately (Soft Delete)
    try {
      const res = await fetch("/api/photos/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids, delete_from_disk: false })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Remove tiles from DOM
        ids.forEach((id) => {
          const tile = document.querySelector(`.photo-tile[data-id="${id}"]`);
          if (tile) {
            const grid = tile.parentElement;
            tile.remove();
            if (grid) {
              const remaining = grid.querySelectorAll(".photo-tile").length;
              const section = grid.closest(".timeline-section");
              if (section) {
                if (remaining === 0) {
                  section.remove();
                } else {
                  const countEl = section.querySelector(".timeline-count");
                  if (countEl) countEl.textContent = `${remaining} item${remaining > 1 ? "s" : ""}`;
                }
              }
            }
          }
        });

        // Remove from state.photos
        state.photos = state.photos.filter((p) => !ids.includes(p.id));
        clearSelection();
        loadTimelineHierarchy();
        updateTrashBadge();

        const toastMsg = count === 1 ? "1 foto dipindahkan ke Tempat Sampah" : `${count} foto dipindahkan ke Tempat Sampah`;
        showToast(toastMsg, "Urungkan", async () => {
          await restorePhotos(ids);
        });
      } else {
        showToast("Gagal memindahkan foto ke tempat sampah", null, null, 3000);
      }
    } catch (e) {
      console.error("Error moving photos to trash", e);
      showToast("Terjadi kesalahan saat menghapus", null, null, 3000);
    }
  }

  async function deleteCurrentLightboxPhoto() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];
    const id = photo.id;
    const filename = photo.filename;

    if (state.currentCategory === "trash") {
      permanentDeleteLightboxPhoto();
      return;
    }

    try {
      const res = await fetch("/api/photos/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: [id], delete_from_disk: false })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Remove tile from DOM
        const tile = document.querySelector(`.photo-tile[data-id="${id}"]`);
        if (tile) {
          const grid = tile.parentElement;
          tile.remove();
          if (grid) {
            const remaining = grid.querySelectorAll(".photo-tile").length;
            const section = grid.closest(".timeline-section");
            if (section) {
              if (remaining === 0) {
                section.remove();
              } else {
                const countEl = section.querySelector(".timeline-count");
                if (countEl) countEl.textContent = `${remaining} item${remaining > 1 ? "s" : ""}`;
              }
            }
          }
        }

        // Remove from state.photos
        state.photos.splice(state.lightboxIndex, 1);
        loadTimelineHierarchy();
        updateTrashBadge();

        if (state.photos.length === 0) {
          closeLightbox();
        } else {
          if (state.lightboxIndex >= state.photos.length) {
            state.lightboxIndex = state.photos.length - 1;
          }
          renderLightboxPhoto();
        }

        showToast(`"${filename}" dipindahkan ke Tempat Sampah`, "Urungkan", async () => {
          await restorePhotos([id]);
        });
      } else {
        showToast("Gagal memindahkan foto ke tempat sampah", null, null, 3000);
      }
    } catch (e) {
      console.error("Error moving photo to trash", e);
      showToast("Terjadi kesalahan saat menghapus", null, null, 3000);
    }
  }

  async function restorePhotos(photoIds) {
    try {
      const res = await fetch("/api/photos/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: photoIds })
      });
      if (res.ok) {
        if (state.currentCategory === "trash") {
          await showTrashView();
        } else {
          await fetchPhotos(true);
        }
        updateTrashBadge();
        loadTimelineHierarchy();
        showToast(`${photoIds.length} item berhasil dipulihkan ke galeri`, null, null, 3000);
      }
    } catch (e) {
      console.error("Error restoring photos", e);
    }
  }

  // --------------------------------------------------------------------------
  // Trash (Tempat Sampah) Management
  // --------------------------------------------------------------------------

  async function updateTrashBadge() {
    try {
      const res = await fetch("/api/photos/trash/count");
      if (!res.ok) return;
      const data = await res.json();
      const total = data.total || 0;
      if (elements.trashBadgeCount) {
        elements.trashBadgeCount.textContent = total;
        if (total > 0) {
          elements.trashBadgeCount.classList.remove("hidden");
        } else {
          elements.trashBadgeCount.classList.add("hidden");
        }
      }
      if (elements.trashCountBadge) {
        elements.trashCountBadge.textContent = `${total} item`;
      }
      if (elements.emptyTrashBtn) {
        elements.emptyTrashBtn.disabled = total === 0;
      }
    } catch (e) {
      console.error("Failed to update trash badge", e);
    }
  }

  async function showTrashView() {
    state.currentCategory = "trash";
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.add("hidden");
    elements.filterBanner.classList.add("hidden");
    elements.trashContainer.classList.remove("hidden");

    clearSelection();
    elements.trashGrid.innerHTML = '<div class="spinner-small" style="margin: 40px auto; grid-column: 1 / -1;"></div>';

    try {
      const res = await fetch("/api/photos/trash?limit=500&offset=0");
      const data = await res.json();
      const photos = data.photos || [];
      state.photos = photos; // Keep in state so Lightbox works on trash photos

      updateTrashBadge();

      if (photos.length === 0) {
        elements.trashGrid.innerHTML = "";
        elements.trashEmptyState.classList.remove("hidden");
        if (elements.emptyTrashBtn) elements.emptyTrashBtn.disabled = true;
      } else {
        elements.trashEmptyState.classList.add("hidden");
        elements.trashGrid.innerHTML = "";
        if (elements.emptyTrashBtn) elements.emptyTrashBtn.disabled = false;

        photos.forEach((photo) => {
          elements.trashGrid.appendChild(createPhotoTile(photo));
        });
      }
    } catch (e) {
      console.error("Failed to load trash photos", e);
      elements.trashGrid.innerHTML = '<div class="empty-state" style="grid-column: 1 / -1;">Error loading trash</div>';
    }
  }

  function hideTrashView() {
    elements.trashContainer.classList.add("hidden");
    clearSelection();
  }

  async function restoreSelectedPhotos() {
    if (state.selectedPhotos.size === 0) return;
    const ids = Array.from(state.selectedPhotos);
    const count = ids.length;

    try {
      const res = await fetch("/api/photos/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        clearSelection();
        await showTrashView();
        loadTimelineHierarchy();
        showToast(`${count} item berhasil dipulihkan ke galeri`, null, null, 3000);
      } else {
        showToast("Gagal memulihkan item", null, null, 3000);
      }
    } catch (e) {
      console.error("Error restoring selected photos", e);
      showToast("Terjadi kesalahan saat memulihkan", null, null, 3000);
    }
  }

  async function permanentDeleteSelectedPhotos() {
    if (state.selectedPhotos.size === 0) return;
    const ids = Array.from(state.selectedPhotos);
    const count = ids.length;

    if (!confirm(`Hapus permanen ${count} item terpilih dari hard disk?\n\nFile media asli, companion JSON metadata Google Takeout, dan file thumbnail WebP akan dihapus selamanya dari disk.`)) {
      return;
    }

    try {
      const res = await fetch("/api/photos/delete-permanent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        clearSelection();
        await showTrashView();
        const m = data.media_files_deleted !== undefined ? data.media_files_deleted : count;
        const j = data.json_files_deleted || 0;
        showToast(`${m} file media & ${j} JSON berhasil dihapus permanen dari disk.`, null, null, 4000);
      } else {
        showToast("Gagal menghapus item dari disk", null, null, 3000);
      }
    } catch (e) {
      console.error("Error permanently deleting photos", e);
      showToast("Terjadi kesalahan saat menghapus dari disk", null, null, 3000);
    }
  }

  function openEmptyTrashModal() {
    if (elements.emptyTrashModalWrapper) {
      elements.emptyTrashModalWrapper.classList.remove("hidden");
    }
  }

  function closeEmptyTrashModal() {
    if (elements.emptyTrashModalWrapper) {
      elements.emptyTrashModalWrapper.classList.add("hidden");
    }
  }

  async function confirmEmptyTrash() {
    if (!elements.emptyTrashModalConfirmBtn) return;
    elements.emptyTrashModalConfirmBtn.disabled = true;
    elements.emptyTrashModalConfirmBtn.textContent = "Mengosongkan sampah dari disk...";

    try {
      const res = await fetch("/api/photos/trash/empty", {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok && data.success) {
        closeEmptyTrashModal();
        await showTrashView();
        const m = data.media_files_deleted !== undefined ? data.media_files_deleted : 0;
        const j = data.json_files_deleted !== undefined ? data.json_files_deleted : 0;
        showToast(`Tempat sampah berhasil dikosongkan: ${m} file media & ${j} JSON dihapus dari disk.`, null, null, 5000);
      } else {
        showToast("Gagal mengosongkan tempat sampah", null, null, 3000);
      }
    } catch (e) {
      console.error("Error emptying trash", e);
      showToast("Terjadi kesalahan saat mengosongkan tempat sampah", null, null, 3000);
    } finally {
      if (elements.emptyTrashModalConfirmBtn) {
        elements.emptyTrashModalConfirmBtn.disabled = false;
        elements.emptyTrashModalConfirmBtn.textContent = "Kosongkan Sampah Sekarang";
      }
    }
  }

  async function restoreLightboxPhoto() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];
    const id = photo.id;

    try {
      const res = await fetch("/api/photos/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: [id] })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        state.photos.splice(state.lightboxIndex, 1);
        updateTrashBadge();
        loadTimelineHierarchy();

        if (state.photos.length === 0) {
          closeLightbox();
          showTrashView();
        } else {
          if (state.lightboxIndex >= state.photos.length) {
            state.lightboxIndex = state.photos.length - 1;
          }
          renderLightboxPhoto();
          showTrashView();
        }
        showToast("Foto berhasil dipulihkan ke galeri", null, null, 3000);
      }
    } catch (e) {
      console.error("Error restoring lightbox photo", e);
    }
  }

  async function permanentDeleteLightboxPhoto() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];
    const id = photo.id;
    const filename = photo.filename;

    if (!confirm(`Hapus permanen "${filename}" dari hard disk?\n\nFile media asli, companion JSON metadata Google Takeout, dan file thumbnail WebP akan dihapus selamanya.`)) {
      return;
    }

    try {
      const res = await fetch("/api/photos/delete-permanent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: [id] })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        state.photos.splice(state.lightboxIndex, 1);
        updateTrashBadge();

        if (state.photos.length === 0) {
          closeLightbox();
          showTrashView();
        } else {
          if (state.lightboxIndex >= state.photos.length) {
            state.lightboxIndex = state.photos.length - 1;
          }
          renderLightboxPhoto();
          showTrashView();
        }
        showToast(`"${filename}" berhasil dihapus permanen dari disk.`, null, null, 4000);
      }
    } catch (e) {
      console.error("Error permanently deleting lightbox photo", e);
    }
  }

  function setupDeleteModalEvents() {
    // Retained for backward compatibility if ever called
  }

  let activeToastTimeout = null;
  function showToast(message, actionLabel = null, actionCallback = null, durationMs = 5000) {
    if (!elements.toastContainer) return;
    elements.toastContainer.innerHTML = "";
    if (activeToastTimeout) clearTimeout(activeToastTimeout);

    const toast = document.createElement("div");
    toast.className = "toast";

    const text = document.createElement("span");
    text.textContent = message;
    toast.appendChild(text);

    if (actionLabel && actionCallback) {
      const actionBtn = document.createElement("button");
      actionBtn.className = "toast-action";
      actionBtn.textContent = actionLabel;
      actionBtn.addEventListener("click", () => {
        toast.classList.add("hiding");
        setTimeout(() => toast.remove(), 250);
        actionCallback();
      });
      toast.appendChild(actionBtn);
    }

    elements.toastContainer.appendChild(toast);

    activeToastTimeout = setTimeout(() => {
      toast.classList.add("hiding");
      setTimeout(() => toast.remove(), 250);
    }, durationMs);
  }

  // --- Album Logic ---

  async function fetchAlbums() {
    elements.albumList.innerHTML = '<div class="spinner-small" style="margin: 0 auto;"></div>';
    try {
      const res = await fetch("/api/albums");
      const albums = await res.json();
      renderAlbumList(albums);
    } catch (e) {
      console.error("Failed to load albums", e);
      elements.albumList.innerHTML = "<div>Error loading albums</div>";
    }
  }

  function renderAlbumList(albums) {
    elements.albumList.innerHTML = "";
    if (!albums || albums.length === 0) {
      elements.albumList.innerHTML = "<div style='color: var(--text-tertiary); text-align: center; padding: 16px; font-size: 0.9rem;'>Belum ada album. Ketik nama album baru di atas lalu klik Buat.</div>";
      return;
    }

    albums.forEach(album => {
      const el = document.createElement("div");
      el.className = "album-item";

      const infoDiv = document.createElement("div");
      infoDiv.className = "album-item-info";

      const iconSpan = document.createElement("span");
      iconSpan.className = "album-item-icon";
      iconSpan.textContent = "📁";

      const textDiv = document.createElement("div");
      const nameDiv = document.createElement("div");
      nameDiv.className = "album-name";
      nameDiv.textContent = album.name;

      const countDiv = document.createElement("div");
      countDiv.className = "album-count";
      countDiv.textContent = `${album.photo_count || 0} foto`;

      textDiv.appendChild(nameDiv);
      textDiv.appendChild(countDiv);

      infoDiv.appendChild(iconSpan);
      infoDiv.appendChild(textDiv);

      const addBtn = document.createElement("span");
      addBtn.className = "album-item-btn";
      addBtn.textContent = "+ Tambahkan";

      el.appendChild(infoDiv);
      el.appendChild(addBtn);

      el.addEventListener("click", () => {
        addSelectedToAlbum(album.id, album.name);
      });
      elements.albumList.appendChild(el);
    });
  }

  async function addSelectedToAlbum(albumId, albumName = "Album") {
    if (state.selectedPhotos.size === 0) return;
    
    const ids = Array.from(state.selectedPhotos);
    try {
      const res = await fetch(`/api/albums/${albumId}/photos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids })
      });
      const data = await res.json();
      if (res.ok) {
        elements.albumModalWrapper.classList.add("hidden");
        const count = data.added_count !== undefined ? data.added_count : ids.length;
        showToast(`${count} foto berhasil ditambahkan ke album "${albumName}"`, null, null, 3500);
        clearSelection();
        if (state.currentCategory === "albums") {
          showAlbumList();
        }
      } else {
        showToast(data.detail || "Gagal menambahkan foto ke album", null, null, 3000);
      }
    } catch (e) {
      console.error("Failed to add photos to album", e);
      showToast("Terjadi kesalahan saat menambahkan foto ke album", null, null, 3000);
    }
  }

  async function createAlbum() {
    const name = elements.newAlbumName.value.trim();
    if (!name) {
      elements.newAlbumName.focus();
      return;
    }

    try {
      elements.createAlbumBtn.disabled = true;
      elements.createAlbumBtn.textContent = "Menyimpan...";

      const res = await fetch("/api/albums", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (res.ok && data.album_id) {
        elements.newAlbumName.value = "";
        
        // If photos are selected, automatically add them to the newly created album!
        if (state.selectedPhotos.size > 0) {
          await addSelectedToAlbum(data.album_id, name);
        } else {
          elements.albumModalWrapper.classList.add("hidden");
          showToast(`Album "${name}" berhasil dibuat`, null, null, 3000);
          if (state.currentCategory === "albums") {
            showAlbumList();
          }
        }
      } else {
        showToast(data.detail || "Gagal membuat album.", null, null, 3000);
      }
    } catch (e) {
      console.error("Failed to create album", e);
      showToast("Terjadi kesalahan saat membuat album.", null, null, 3000);
    } finally {
      elements.createAlbumBtn.disabled = false;
      elements.createAlbumBtn.textContent = "Buat & Tambahkan";
    }
  }

  // --- Album Gallery View ---
  let currentAlbumId = null;

  async function showAlbumList() {
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.remove("hidden");
    
    elements.albumTitle.textContent = "Semua Album";
    elements.albumBackBtn.style.display = "none";
    elements.deleteAlbumBtn.style.display = "none";
    elements.albumGrid.innerHTML = '<div class="spinner-small" style="margin: 40px auto;"></div>';
    
    try {
      const res = await fetch("/api/albums");
      const albums = await res.json();
      renderAlbumsGallery(albums);
    } catch (e) {
      console.error("Failed to load albums for gallery", e);
      elements.albumGrid.innerHTML = "<div class='empty-state'>Error loading albums</div>";
    }
  }

  function hideAlbumView() {
    elements.timelineContainer.classList.remove("hidden");
    elements.timelineScrubber.classList.remove("hidden");
    elements.albumContainer.classList.add("hidden");
    currentAlbumId = null;
  }

  function renderAlbumsGallery(albums) {
    elements.albumGrid.innerHTML = "";
    if (!albums || albums.length === 0) {
      elements.albumGrid.innerHTML = "<div class='empty-state'><h3>Belum ada album</h3><p>Pilih foto dari timeline lalu klik 'Tambahkan ke Album' untuk membuat album.</p></div>";
      return;
    }
    
    albums.forEach(album => {
      const card = document.createElement("div");
      card.className = "album-card";
      card.innerHTML = `
        <div class="album-card-icon">📁</div>
        <h3 class="album-card-title">${album.name}</h3>
        <div class="album-card-count">${album.photo_count || 0} foto</div>
      `;
      card.addEventListener("click", () => openAlbum(album.id, album.name));
      elements.albumGrid.appendChild(card);
    });
  }

  async function openAlbum(albumId, albumName) {
    currentAlbumId = albumId;
    elements.albumTitle.textContent = albumName;
    elements.albumBackBtn.style.display = "inline-flex";
    elements.deleteAlbumBtn.style.display = "inline-flex";
    elements.albumGrid.innerHTML = '<div class="spinner-small" style="margin: 40px auto;"></div>';
    
    try {
      const res = await fetch(`/api/albums/${albumId}/photos?limit=500&offset=0`);
      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }
      const data = await res.json();
      state.photos = data.photos || []; // Set state.photos so lightbox works
      renderAlbumPhotos(state.photos);
    } catch (e) {
      console.error("Failed to load album photos", e);
      elements.albumGrid.innerHTML = "<div class='empty-state'><h3>Gagal memuat foto album</h3><p>Terjadi kesalahan saat mengambil foto album.</p></div>";
    }
  }

  function renderAlbumPhotos(photos) {
    elements.albumGrid.innerHTML = "";
    if (!photos || photos.length === 0) {
      elements.albumGrid.innerHTML = "<div class='empty-state'><h3>Album masih kosong</h3><p>Pilih foto dari linimasa dan tambahkan ke album ini.</p></div>";
      return;
    }
    
    photos.forEach((photo) => {
      const tile = createPhotoTile(photo);
      elements.albumGrid.appendChild(tile);
    });
  }

  elements.albumBackBtn.addEventListener("click", () => {
    showAlbumList();
  });

  elements.deleteAlbumBtn.addEventListener("click", async () => {
    if (!currentAlbumId) return;
    if (!confirm(`Are you sure you want to delete this album? Your original photos will NOT be deleted.`)) return;
    
    try {
      const res = await fetch(`/api/albums/${currentAlbumId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        showAlbumList();
      }
    } catch (e) {
      console.error("Failed to delete album", e);
    }
  });

  // End of Album Logic

  // ==========================================================================
  // Photo Map & Geolocation System (Leaflet.js + MarkerCluster)
  // ==========================================================================
  let photoMapInstance = null;
  let photoMapTileLayer = null;
  let photoMapClusterGroup = null;
  let lightboxMiniMapInstance = null;
  let lightboxMiniMapMarker = null;
  let geoPointsCache = null;

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getMapTileUrl() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return isDark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
  }

  function updateMapTilesTheme() {
    if (photoMapTileLayer) {
      photoMapTileLayer.setUrl(getMapTileUrl());
    }
  }

  function initPhotoMap() {
    if (photoMapInstance || typeof L === "undefined" || !elements.photoMapCanvas) return;

    photoMapInstance = L.map(elements.photoMapCanvas, {
      center: [-2.5, 118], // Center of Indonesia
      zoom: 5,
      maxZoom: 18,
      zoomControl: true,
    });

    photoMapTileLayer = L.tileLayer(getMapTileUrl(), {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: "abcd",
    }).addTo(photoMapInstance);

    photoMapClusterGroup = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 45,
      spiderfyOnMaxZoom: true,
      iconCreateFunction: function (cluster) {
        const count = cluster.getChildCount();
        let size = count < 10 ? 34 : count < 100 ? 42 : 50;
        return L.divIcon({
          html: `<span>${count}</span>`,
          className: "custom-cluster-marker",
          iconSize: L.point(size, size),
        });
      },
    });

    photoMapInstance.addLayer(photoMapClusterGroup);

    photoMapInstance.on("moveend", () => {
      updateMapTrayPhotos();
    });
  }

  async function loadGeoPoints() {
    if (!elements.mapCountBadge) return;
    elements.mapCountBadge.textContent = "Memuat lokasi...";

    try {
      const res = await fetch("/api/geo/points");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      geoPointsCache = data.points || [];

      elements.mapCountBadge.textContent = `${geoPointsCache.length.toLocaleString()} foto berlokasi`;

      if (photoMapClusterGroup) {
        photoMapClusterGroup.clearLayers();

        const markers = [];
        const pinIcon = L.divIcon({
          className: "custom-pin-marker",
          html: `<svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5" fill="#fff"/></svg>`,
          iconSize: [28, 28],
          iconAnchor: [14, 28],
          popupAnchor: [0, -28],
        });

        geoPointsCache.forEach((p) => {
          const marker = L.marker([p.latitude, p.longitude], { icon: pinIcon });
          const popupContent = `
            <div class="map-popup-card" onclick="window.__openPhotoById(${p.id})">
              <img class="map-popup-thumb" src="/api/thumbnails/${p.id}" loading="lazy" alt="${escapeHtml(p.filename)}" onerror="this.src='/api/media/${p.id}'" />
              <div class="map-popup-meta">
                <div class="map-popup-date">${p.taken_formatted || "Foto"}</div>
                <div class="map-popup-name">${escapeHtml(p.filename)}</div>
              </div>
              <button class="map-popup-btn" type="button">Buka Foto</button>
            </div>
          `;
          marker.bindPopup(popupContent, { maxWidth: 220, closeButton: false });
          markers.push(marker);
        });

        photoMapClusterGroup.addLayers(markers);

        if (markers.length > 0 && photoMapInstance) {
          photoMapInstance.fitBounds(photoMapClusterGroup.getBounds().pad(0.08));
        }
      }
    } catch (e) {
      console.error("Gagal memuat geo points", e);
      elements.mapCountBadge.textContent = "Gagal memuat lokasi";
    }
  }

  async function showPhotoMapView(centerTarget, zoomLevel, targetPhotoId) {
    state.currentCategory = "map";
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.add("hidden");
    elements.trashContainer.classList.add("hidden");
    elements.filterBanner.classList.add("hidden");
    elements.mapContainer.classList.remove("hidden");

    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    if (elements.mapChip) elements.mapChip.classList.add("active");

    if (!photoMapInstance) {
      initPhotoMap();
    }

    setTimeout(() => {
      if (photoMapInstance) {
        photoMapInstance.invalidateSize();
        if (centerTarget) {
          photoMapInstance.setView(centerTarget, zoomLevel || 16, { animate: true });
        }
      }
    }, 120);

    if (!geoPointsCache) {
      await loadGeoPoints();
    } else if (!centerTarget && photoMapClusterGroup && photoMapClusterGroup.getLayers().length > 0) {
      photoMapInstance.fitBounds(photoMapClusterGroup.getBounds().pad(0.08));
    }

    if (centerTarget && photoMapInstance) {
      photoMapInstance.setView(centerTarget, zoomLevel || 16, { animate: true });
    }

    updateMapTrayPhotos();
  }

  function hidePhotoMapView() {
    elements.mapContainer.classList.add("hidden");
  }

  function updateMapTrayPhotos() {
    if (!photoMapInstance || !geoPointsCache || !elements.mapTrayGrid) return;
    const bounds = photoMapInstance.getBounds();
    const inView = geoPointsCache.filter((p) => bounds.contains([p.latitude, p.longitude]));

    if (elements.mapTrayCount) {
      elements.mapTrayCount.textContent = `${inView.length} foto`;
    }

    elements.mapTrayGrid.innerHTML = "";
    if (inView.length === 0) {
      elements.mapTrayGrid.innerHTML = `<div class="map-tray-empty">Tidak ada foto di area peta ini. Geser atau perkecil peta.</div>`;
      return;
    }

    // Limit to 60 photos in tray for optimal performance
    const displayPhotos = inView.slice(0, 60);
    displayPhotos.forEach((photo) => {
      const item = document.createElement("div");
      item.className = "map-tray-item";
      item.title = `${photo.filename} (${photo.taken_formatted || "Foto"})`;
      item.innerHTML = `<img src="/api/thumbnails/${photo.id}" loading="lazy" alt="${escapeHtml(photo.filename)}" onerror="this.src='/api/media/${photo.id}'" />`;
      item.addEventListener("click", () => {
        openLightbox(photo.id);
      });
      elements.mapTrayGrid.appendChild(item);
    });
  }

  function updateLightboxMiniMap(lat, lng) {
    if (typeof L === "undefined" || !elements.lightboxMiniMap) return;

    if (!lightboxMiniMapInstance) {
      lightboxMiniMapInstance = L.map(elements.lightboxMiniMap, {
        zoomControl: false,
        attributionControl: false,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        touchZoom: false,
      });

      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        { maxZoom: 18, subdomains: "abcd" }
      ).addTo(lightboxMiniMapInstance);
    }

    if (lightboxMiniMapMarker) {
      lightboxMiniMapMarker.setLatLng([lat, lng]);
    } else {
      const pinIcon = L.divIcon({
        className: "custom-pin-marker",
        html: `<svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5" fill="#fff"/></svg>`,
        iconSize: [26, 26],
        iconAnchor: [13, 26],
      });
      lightboxMiniMapMarker = L.marker([lat, lng], { icon: pinIcon }).addTo(
        lightboxMiniMapInstance
      );
    }

    lightboxMiniMapInstance.setView([lat, lng], 14);
    setTimeout(() => {
      if (lightboxMiniMapInstance) {
        lightboxMiniMapInstance.invalidateSize();
        lightboxMiniMapInstance.setView([lat, lng], 14);
      }
    }, 150);
  }

  // --- Bootstrap ---
  init();
})();
