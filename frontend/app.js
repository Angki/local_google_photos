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
    isSlideshowPlaying: false,
    slideshowTimer: null,
    scannerStatus: null,
    ws: null,
    selectedPhotos: new Set(),
    lastSelectedId: null,
    memories: [],
    duplicateGroups: [],
    selectedDuplicates: new Set(),
    isLivePhotoPlaying: false,
    editState: {
      rotate: 0,
      flip_h: false,
      brightness: 0,
      contrast: 0,
      saturation: 0,
      warmth: 0,
      auto_enhance: false,
    },
    editingPhoto: null,
    lockedToken: null,
    lockedPinInput: "",
    isPinSetupMode: false,
    pinSetupFirstPass: "",
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
    shortcutsHelpBtn: document.getElementById("shortcutsHelpBtn"),
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
    lightboxFavoriteBtn: document.getElementById("lightboxFavoriteBtn"),
    lightboxSlideshowBtn: document.getElementById("lightboxSlideshowBtn"),
    lightboxDownloadBtn: document.getElementById("lightboxDownloadBtn"),
    lightboxInfoToggleBtn: document.getElementById("lightboxInfoToggleBtn"),
    lightboxOpenLocalBtn: document.getElementById("lightboxOpenLocalBtn"),
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
    favoriteSelectedBtn: document.getElementById("favoriteSelectedBtn"),
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

    // Keyboard Shortcuts Modal
    shortcutsModalWrapper: document.getElementById("shortcutsModalWrapper"),
    shortcutsModalBackdrop: document.getElementById("shortcutsModalBackdrop"),
    shortcutsModalCloseBtn: document.getElementById("shortcutsModalCloseBtn"),

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

    // Memories (Fase 1)
    memoriesSection: document.getElementById("memoriesSection"),
    memoriesCarousel: document.getElementById("memoriesCarousel"),
    infoLocationName: document.getElementById("infoLocationName"),

    // Duplicates (Fase 2)
    duplicatesChip: document.getElementById("duplicatesChip"),
    duplicatesBadgeCount: document.getElementById("duplicatesBadgeCount"),
    duplicatesContainer: document.getElementById("duplicatesContainer"),
    duplicatesBackBtn: document.getElementById("duplicatesBackBtn"),
    duplicatesSummaryBadge: document.getElementById("duplicatesSummaryBadge"),
    duplicatesAutoSelectBtn: document.getElementById("duplicatesAutoSelectBtn"),
    duplicatesDeleteSelectedBtn: document.getElementById("duplicatesDeleteSelectedBtn"),
    duplicatesSelectedCount: document.getElementById("duplicatesSelectedCount"),
    duplicatesGroupsList: document.getElementById("duplicatesGroupsList"),
    duplicatesEmptyState: document.getElementById("duplicatesEmptyState"),

    // Live Photo (Fase 3)
    lightboxLiveBtn: document.getElementById("lightboxLiveBtn"),

    // Photo Studio & Editor (Fase 6)
    lightboxEditBtn: document.getElementById("lightboxEditBtn"),
    editorModalWrapper: document.getElementById("editorModalWrapper"),
    editorModalBackdrop: document.getElementById("editorModalBackdrop"),
    editorCloseBtn: document.getElementById("editorCloseBtn"),
    editorFilename: document.getElementById("editorFilename"),
    editorResetBtn: document.getElementById("editorResetBtn"),
    editorSaveCopyBtn: document.getElementById("editorSaveCopyBtn"),
    editorPreviewImg: document.getElementById("editorPreviewImg"),
    tabTuneBtn: document.getElementById("tabTuneBtn"),
    tabTransformBtn: document.getElementById("tabTransformBtn"),
    panelTune: document.getElementById("panelTune"),
    panelTransform: document.getElementById("panelTransform"),
    editorAutoEnhanceBtn: document.getElementById("editorAutoEnhanceBtn"),
    sliderBrightness: document.getElementById("sliderBrightness"),
    valBrightness: document.getElementById("valBrightness"),
    sliderContrast: document.getElementById("sliderContrast"),
    valContrast: document.getElementById("valContrast"),
    sliderSaturation: document.getElementById("sliderSaturation"),
    valSaturation: document.getElementById("valSaturation"),
    sliderWarmth: document.getElementById("sliderWarmth"),
    valWarmth: document.getElementById("valWarmth"),
    btnRotate90: document.getElementById("btnRotate90"),
    btnFlipH: document.getElementById("btnFlipH"),

    // LAN & Mobile QR Code Access (Phase 9)
    lanShareBtn: document.getElementById("lanShareBtn"),
    lanModalWrapper: document.getElementById("lanModalWrapper"),
    lanModalBackdrop: document.getElementById("lanModalBackdrop"),
    lanModalCloseBtn: document.getElementById("lanModalCloseBtn"),
    lanQrContainer: document.getElementById("lanQrContainer"),
    lanUrlInput: document.getElementById("lanUrlInput"),
    lanCopyUrlBtn: document.getElementById("lanCopyUrlBtn"),

    // Locked Folder (Phase 9)
    lockedChip: document.getElementById("lockedChip"),
    lockedBadgeCount: document.getElementById("lockedBadgeCount"),
    lockedContainer: document.getElementById("lockedContainer"),
    lockedBackBtn: document.getElementById("lockedBackBtn"),
    lockedRelockBtn: document.getElementById("lockedRelockBtn"),
    lockedCountBadge: document.getElementById("lockedCountBadge"),
    lockedGrid: document.getElementById("lockedGrid"),
    lockedEmptyState: document.getElementById("lockedEmptyState"),
    lockSelectedBtn: document.getElementById("lockSelectedBtn"),
    lightboxLockBtn: document.getElementById("lightboxLockBtn"),
    lightboxUnlockBtn: document.getElementById("lightboxUnlockBtn"),
    pinModalWrapper: document.getElementById("pinModalWrapper"),
    pinModalBackdrop: document.getElementById("pinModalBackdrop"),
    pinModalCloseBtn: document.getElementById("pinModalCloseBtn"),
    pinModalTitle: document.getElementById("pinModalTitle"),
    pinModalSubtitle: document.getElementById("pinModalSubtitle"),
    pinDotsRow: document.getElementById("pinDotsRow"),
    pinDot0: document.getElementById("pinDot0"),
    pinDot1: document.getElementById("pinDot1"),
    pinDot2: document.getElementById("pinDot2"),
    pinDot3: document.getElementById("pinDot3"),
    pinErrorText: document.getElementById("pinErrorText"),
    keypadClearBtn: document.getElementById("keypadClearBtn"),
    keypadBackspaceBtn: document.getElementById("keypadBackspaceBtn"),

    // OCR / Live Text (Phase 9)
    lightboxOcrBtn: document.getElementById("lightboxOcrBtn"),
    ocrModalWrapper: document.getElementById("ocrModalWrapper"),
    ocrModalBackdrop: document.getElementById("ocrModalBackdrop"),
    ocrModalCloseBtn: document.getElementById("ocrModalCloseBtn"),
    ocrLoadingState: document.getElementById("ocrLoadingState"),
    ocrTextContainer: document.getElementById("ocrTextContainer"),
    ocrTextarea: document.getElementById("ocrTextarea"),
    ocrCharCount: document.getElementById("ocrCharCount"),
    ocrCopyBtn: document.getElementById("ocrCopyBtn"),
  };

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------
  function init() {
    setupTheme();
    initPWA();
    setupEventListeners();
    setupWebSocket();
    setupIntersectionObserver();
    setupScrollSpy();
    loadTimelineHierarchy();
    updateTrashBadge();
    updateDuplicatesBadge();
    updateLockedBadge();
    loadMemories();
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
    if (status.event === "photo_added") {
      showToast(`Foto baru terdeteksi: ${status.filename} ✨`, null, null, 3500);
      loadTimelineHierarchy();
      return;
    }

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
          } else if (state.currentCategory === "favorites") {
            params.append("is_favorite", "true");
          } else {
            params.append("category", state.currentCategory);
          }
        }
        url = `/api/photos?${params.toString()}`;

        if (state.currentCategory !== "all") {
          elements.filterBanner.classList.remove("hidden");
          if (state.currentCategory === "favorites") {
            elements.filterDesc.textContent = "Showing ⭐ FAVORITES";
          } else {
            elements.filterDesc.textContent = `Showing ${state.currentCategory.toUpperCase()}`;
          }
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
      if (elements.memoriesSection) elements.memoriesSection.classList.add("hidden");
      return;
    }

    elements.emptyState.classList.add("hidden");

    // Manage memories visibility on gallery reset
    if (elements.memoriesSection) {
      if (state.currentCategory === "all" && !state.searchQuery && !state.currentYear && !state.currentMonth && state.memories && state.memories.length > 0) {
        elements.memoriesSection.classList.remove("hidden");
      } else {
        elements.memoriesSection.classList.add("hidden");
      }
    }

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
      const locDisplay = photo.location_label || (photo.city ? `${photo.city}, ${photo.country || ""}` : "Ada data lokasi (GPS)");
      geoBadge.title = locDisplay;
      geoBadge.innerHTML = `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`;
      tile.appendChild(geoBadge);
    }

    // Live Photo / Motion Photo Badge
    if (photo.is_live_photo) {
      const liveBadge = document.createElement("div");
      liveBadge.className = "live-photo-badge";
      liveBadge.innerHTML = `<span class="live-circle">◉</span> LIVE`;
      tile.appendChild(liveBadge);
    }

    // Favorite Star Badge
    if (photo.is_favorite) {
      const favBadge = document.createElement("div");
      favBadge.className = "favorite-badge";
      favBadge.title = "Favorit (⭐)";
      favBadge.textContent = "⭐";
      tile.appendChild(favBadge);
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
    stopSlideshow();
    stopLivePhotoPlayback();
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

    stopLivePhotoPlayback();

    elements.lightboxDate.textContent = photo.taken_formatted || "Unknown Date";
    elements.lightboxFilename.textContent = photo.filename;

    if (photo.media_type === "video") {
      if (elements.lightboxLiveBtn) elements.lightboxLiveBtn.classList.add("hidden");
      if (elements.lightboxEditBtn) elements.lightboxEditBtn.classList.add("hidden");
      elements.lightboxImg.classList.add("hidden");
      elements.lightboxImg.classList.remove("ken-burns");
      elements.lightboxVideo.classList.remove("hidden");
      if (elements.lightboxOpenLocalBtn) elements.lightboxOpenLocalBtn.style.display = "inline-flex";

      // Reset and reload video stream cleanly
      elements.lightboxVideo.pause();
      elements.lightboxVideo.muted = false;
      elements.lightboxVideo.src = `/api/media/${photo.id}`;
      elements.lightboxVideo.load();

      const playPromise = elements.lightboxVideo.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Autoplay with audio blocked by browser policy, muting for instant playback:", err);
          elements.lightboxVideo.muted = true;
          elements.lightboxVideo.play().catch(() => {});
        });
      }

      elements.lightboxVideo.onerror = () => {
        console.warn("Video failed to play in browser (codec incompatibility or network error)");
        showToast("Browser tidak dapat mendecode video ini. Klik tombol layar di kanan atas untuk memutar di aplikasi video laptop.");
      };
    } else {
      if (elements.lightboxEditBtn) elements.lightboxEditBtn.classList.remove("hidden");
      elements.lightboxVideo.classList.add("hidden");
      elements.lightboxVideo.pause();
      elements.lightboxVideo.src = "";
      if (elements.lightboxOpenLocalBtn) elements.lightboxOpenLocalBtn.style.display = "none";
      elements.lightboxImg.classList.remove("hidden");
      elements.lightboxImg.src = `/api/media/${photo.id}`;

      // Ken Burns Cinematic Animation during Slideshow
      if (state.isSlideshowPlaying) {
        elements.lightboxImg.classList.remove("ken-burns");
        void elements.lightboxImg.offsetWidth;
        elements.lightboxImg.classList.add("ken-burns");
      } else {
        elements.lightboxImg.classList.remove("ken-burns");
      }

      // Live Photo Toggle Button
      if (elements.lightboxLiveBtn) {
        if (photo.is_live_photo) {
          elements.lightboxLiveBtn.classList.remove("hidden");
          elements.lightboxLiveBtn.classList.remove("playing");
          elements.lightboxLiveBtn.onclick = () => toggleLivePhotoPlayback(photo);
        } else {
          elements.lightboxLiveBtn.classList.add("hidden");
        }
      }
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

    // Geolocation & Reverse Geocoded Location Label
    if (photo.has_geo && photo.latitude && photo.longitude) {
      elements.infoGeoBlock.classList.remove("hidden");
      if (elements.infoLocationName) {
        if (photo.location_label || photo.city) {
          const locParts = [photo.city, photo.state, photo.country].filter(Boolean);
          const locDisplay = photo.location_label || locParts.join(", ");
          elements.infoLocationName.textContent = `📍 ${locDisplay}`;
          elements.infoLocationName.classList.remove("hidden");
        } else {
          elements.infoLocationName.classList.add("hidden");
        }
      }
      elements.infoGeoCoords.textContent = `${photo.latitude.toFixed(5)}, ${photo.longitude.toFixed(5)}`;
      elements.infoMapsLink.href = `https://www.google.com/maps?q=${photo.latitude},${photo.longitude}`;
      updateLightboxMiniMap(photo.latitude, photo.longitude);
    } else {
      elements.infoGeoBlock.classList.add("hidden");
      if (elements.infoLocationName) {
        elements.infoLocationName.classList.add("hidden");
      }
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

    if (elements.lightboxOpenLocalBtn) {
      elements.lightboxOpenLocalBtn.onclick = async () => {
        try {
          const res = await fetch(`/api/media/${photo.id}/open-local`, { method: "POST" });
          if (res.ok) {
            showToast("Video dibuka di pemutar aplikasi laptop (VLC/Default)");
          } else {
            window.open(`/api/media/${photo.id}`, "_blank");
          }
        } catch (e) {
          window.open(`/api/media/${photo.id}`, "_blank");
        }
      };
    }

    // Update Favorite button active state
    if (elements.lightboxFavoriteBtn) {
      elements.lightboxFavoriteBtn.classList.toggle("starred", Boolean(photo.is_favorite));
      elements.lightboxFavoriteBtn.title = photo.is_favorite ? "Hapus dari Favorit (f)" : "Tandai Favorit (f)";
    }

    // OCR & Locked status in Lightbox
    if (elements.lightboxOcrBtn) {
      elements.lightboxOcrBtn.style.display = photo.media_type === "video" ? "none" : "inline-flex";
    }

    if (photo.is_locked || state.currentCategory === "locked") {
      if (elements.lightboxLockBtn) elements.lightboxLockBtn.style.display = "none";
      if (elements.lightboxUnlockBtn) elements.lightboxUnlockBtn.style.display = "inline-flex";
    } else {
      if (elements.lightboxLockBtn) elements.lightboxLockBtn.style.display = "inline-flex";
      if (elements.lightboxUnlockBtn) elements.lightboxUnlockBtn.style.display = "none";
    }

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

  async function toggleLightboxFavorite() {
    const photo = state.photos[state.lightboxIndex];
    if (!photo) return;

    try {
      const res = await fetch(`/api/photos/${photo.id}/favorite`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        photo.is_favorite = data.is_favorite;
        if (elements.lightboxFavoriteBtn) {
          elements.lightboxFavoriteBtn.classList.toggle("starred", Boolean(photo.is_favorite));
          elements.lightboxFavoriteBtn.title = photo.is_favorite ? "Hapus dari Favorit (f)" : "Tandai Favorit (f)";
        }
        // Update DOM tile if present in current view
        const tile = document.querySelector(`.photo-tile[data-id="${photo.id}"]`);
        if (tile) {
          let badge = tile.querySelector(".favorite-badge");
          if (photo.is_favorite) {
            if (!badge) {
              badge = document.createElement("div");
              badge.className = "favorite-badge";
              badge.title = "Favorit (⭐)";
              badge.textContent = "⭐";
              tile.appendChild(badge);
            }
          } else if (badge) {
            badge.remove();
          }
        }
        showToast(photo.is_favorite ? "Ditambahkan ke Favorit ⭐" : "Dihapus dari Favorit", null, null, 2500);
      }
    } catch (e) {
      console.error("Error toggling favorite", e);
      showToast("Gagal mengubah status favorit", null, null, 2500);
    }
  }

  function downloadLightboxPhoto() {
    const photo = state.photos[state.lightboxIndex];
    if (!photo) return;
    const downloadUrl = `/api/media/${photo.id}`;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = photo.filename || `photo_${photo.id}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast(`Mengunduh "${photo.filename}"...`, null, null, 2500);
  }

  function toggleLightboxSlideshow() {
    if (state.isSlideshowPlaying) {
      stopSlideshow();
      showToast("Tayangan Slide dijeda", null, null, 2000);
    } else {
      startSlideshow();
      showToast("Tayangan Slide dimulai (3.5s) ▶", null, null, 2000);
    }
  }

  function startSlideshow() {
    state.isSlideshowPlaying = true;
    if (elements.lightboxSlideshowBtn) {
      elements.lightboxSlideshowBtn.classList.add("playing");
      elements.lightboxSlideshowBtn.title = "Jeda Tayangan Slide (Space)";
      elements.lightboxSlideshowBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="6" y="4" width="4" height="16"></rect>
          <rect x="14" y="4" width="4" height="16"></rect>
        </svg>`;
    }
    if (elements.lightboxImg) {
      elements.lightboxImg.classList.remove("ken-burns");
      void elements.lightboxImg.offsetWidth;
      elements.lightboxImg.classList.add("ken-burns");
    }
    if (state.slideshowTimer) clearInterval(state.slideshowTimer);
    state.slideshowTimer = setInterval(() => {
      if (elements.lightboxModal.classList.contains("hidden")) {
        stopSlideshow();
        return;
      }
      if (state.lightboxIndex < state.photos.length - 1) {
        navigateLightbox(1);
      } else {
        state.lightboxIndex = 0;
        renderLightboxPhoto();
      }
    }, 4000);
  }

  function stopSlideshow() {
    state.isSlideshowPlaying = false;
    if (state.slideshowTimer) {
      clearInterval(state.slideshowTimer);
      state.slideshowTimer = null;
    }
    if (elements.lightboxImg) {
      elements.lightboxImg.classList.remove("ken-burns");
    }
    if (elements.lightboxSlideshowBtn) {
      elements.lightboxSlideshowBtn.classList.remove("playing");
      elements.lightboxSlideshowBtn.title = "Tayangan Slide (Space)";
      elements.lightboxSlideshowBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>`;
    }
  }

  async function favoriteSelectedPhotos(isFavorite = true) {
    const photoIds = Array.from(state.selectedPhotos);
    if (photoIds.length === 0) return;

    try {
      const res = await fetch("/api/photos/favorite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: photoIds, is_favorite: isFavorite }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update state in memory
        state.photos.forEach((p) => {
          if (photoIds.includes(p.id)) {
            p.is_favorite = isFavorite;
          }
        });
        // Update tiles in DOM
        photoIds.forEach((id) => {
          const tile = document.querySelector(`.photo-tile[data-id="${id}"]`);
          if (tile) {
            let badge = tile.querySelector(".favorite-badge");
            if (isFavorite) {
              if (!badge) {
                badge = document.createElement("div");
                badge.className = "favorite-badge";
                badge.title = "Favorit (⭐)";
                badge.textContent = "⭐";
                tile.appendChild(badge);
              }
            } else if (badge) {
              badge.remove();
            }
          }
        });
        clearSelection();
        showToast(
          isFavorite
            ? `${data.updated_count} foto ditandai Favorit ⭐`
            : `${data.updated_count} foto dihapus dari Favorit`,
          null,
          null,
          3000
        );
      }
    } catch (e) {
      console.error("Error batch favoriting photos", e);
      showToast("Gagal memperbarui status favorit", null, null, 3000);
    }
  }

  function openShortcutsModal() {
    if (elements.shortcutsModalWrapper) {
      elements.shortcutsModalWrapper.classList.remove("hidden");
    }
  }

  function closeShortcutsModal() {
    if (elements.shortcutsModalWrapper) {
      elements.shortcutsModalWrapper.classList.add("hidden");
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
        hideDuplicatesView();
        hideLockedView();
        showTrashView();
      } else if (state.currentCategory === "albums") {
        hideTrashView();
        hidePhotoMapView();
        hideDuplicatesView();
        hideLockedView();
        showAlbumList();
      } else if (state.currentCategory === "map") {
        hideTrashView();
        hideAlbumView();
        hideDuplicatesView();
        hideLockedView();
        showPhotoMapView();
      } else if (state.currentCategory === "duplicates") {
        hideTrashView();
        hideAlbumView();
        hidePhotoMapView();
        hideLockedView();
        showDuplicatesView();
      } else if (state.currentCategory === "locked") {
        hideTrashView();
        hideAlbumView();
        hidePhotoMapView();
        hideDuplicatesView();
        openLockedFolderWithPin();
      } else {
        hideTrashView();
        hideAlbumView();
        hidePhotoMapView();
        hideDuplicatesView();
        hideLockedView();
        fetchPhotos(true);
      }
    });

    // Lightbox events
    elements.lightboxBackBtn.addEventListener("click", closeLightbox);
    elements.lightboxBackdrop.addEventListener("click", closeLightbox);
    elements.navPrevBtn.addEventListener("click", () => navigateLightbox(-1));
    elements.navNextBtn.addEventListener("click", () => navigateLightbox(1));

    if (elements.lightboxFavoriteBtn) {
      elements.lightboxFavoriteBtn.addEventListener("click", toggleLightboxFavorite);
    }
    if (elements.lightboxSlideshowBtn) {
      elements.lightboxSlideshowBtn.addEventListener("click", toggleLightboxSlideshow);
    }
    if (elements.lightboxDownloadBtn) {
      elements.lightboxDownloadBtn.addEventListener("click", downloadLightboxPhoto);
    }
    if (elements.lightboxEditBtn) {
      elements.lightboxEditBtn.addEventListener("click", () => openPhotoEditor());
    }

    elements.lightboxInfoToggleBtn.addEventListener("click", () => {
      elements.infoSidebar.classList.toggle("open");
    });
    elements.closeSidebarBtn.addEventListener("click", () => {
      elements.infoSidebar.classList.remove("open");
    });

    // Keyboard navigation
    window.addEventListener("keydown", (e) => {
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
      if (activeTag === "input" || activeTag === "textarea") {
        if (e.key === "Escape") document.activeElement.blur();
        return;
      }

      // Close editor modal if open
      if (elements.editorModalWrapper && !elements.editorModalWrapper.classList.contains("hidden")) {
        if (e.key === "Escape") {
          closePhotoEditor();
          return;
        }
      }

      // Close shortcuts modal if open
      if (elements.shortcutsModalWrapper && !elements.shortcutsModalWrapper.classList.contains("hidden")) {
        if (e.key === "Escape") {
          closeShortcutsModal();
          return;
        }
      }

      if (!elements.lightboxModal.classList.contains("hidden")) {
        if (e.key === "Escape") closeLightbox();
        else if (e.key === "ArrowLeft") navigateLightbox(-1);
        else if (e.key === "ArrowRight") navigateLightbox(1);
        else if (e.key === "Delete" || e.key === "Backspace") {
          deleteCurrentLightboxPhoto();
        } else if (e.key.toLowerCase() === "i") {
          elements.infoSidebar.classList.toggle("open");
        } else if (e.key.toLowerCase() === "f") {
          toggleLightboxFavorite();
        } else if (e.key.toLowerCase() === "d") {
          downloadLightboxPhoto();
        } else if (e.key.toLowerCase() === "e") {
          openPhotoEditor();
        } else if (e.key.toLowerCase() === "l") {
          toggleLivePhotoPlayback();
        } else if (e.key === " ") {
          e.preventDefault();
          toggleLightboxSlideshow();
        }
      } else if (state.selectedPhotos.size > 0 && e.key === "Escape") {
        clearSelection();
      } else if (e.key === "?" || e.key.toLowerCase() === "h") {
        e.preventDefault();
        openShortcutsModal();
      }
    });

    // Shortcuts modal button events
    if (elements.shortcutsHelpBtn) {
      elements.shortcutsHelpBtn.addEventListener("click", openShortcutsModal);
    }
    if (elements.shortcutsModalCloseBtn) {
      elements.shortcutsModalCloseBtn.addEventListener("click", closeShortcutsModal);
    }
    if (elements.shortcutsModalBackdrop) {
      elements.shortcutsModalBackdrop.addEventListener("click", closeShortcutsModal);
    }

    // --- Selection & Album Events ---
    elements.cancelSelectionBtn.addEventListener("click", clearSelection);
    if (elements.selectAllVisibleBtn) {
      elements.selectAllVisibleBtn.addEventListener("click", selectAllVisiblePhotos);
    }
    if (elements.favoriteSelectedBtn) {
      elements.favoriteSelectedBtn.addEventListener("click", () => favoriteSelectedPhotos(true));
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

    // --- Duplicates View Events ---
    if (elements.duplicatesBackBtn) {
      elements.duplicatesBackBtn.addEventListener("click", () => {
        hideDuplicatesView();
        state.currentCategory = "all";
        document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        const allChip = document.querySelector('[data-category="all"]');
        if (allChip) allChip.classList.add("active");
        elements.timelineContainer.classList.remove("hidden");
        elements.timelineScrubber.classList.remove("hidden");
        fetchPhotos(true);
      });
    }

    if (elements.duplicatesAutoSelectBtn) {
      elements.duplicatesAutoSelectBtn.addEventListener("click", autoSelectDuplicates);
    }

    if (elements.duplicatesDeleteSelectedBtn) {
      elements.duplicatesDeleteSelectedBtn.addEventListener("click", deleteSelectedDuplicates);
    }

    // --- Mobile Touch Gestures for Lightbox (Swipe to navigate, swipe down to close) ---
    let touchStartX = 0;
    let touchStartY = 0;
    let touchEndX = 0;
    let touchEndY = 0;

    elements.lightboxModal.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length === 1) {
          touchStartX = e.touches[0].clientX;
          touchStartY = e.touches[0].clientY;
        }
      },
      { passive: true }
    );

    elements.lightboxModal.addEventListener(
      "touchend",
      (e) => {
        if (e.changedTouches.length === 1) {
          touchEndX = e.changedTouches[0].clientX;
          touchEndY = e.changedTouches[0].clientY;

          const deltaX = touchEndX - touchStartX;
          const deltaY = touchEndY - touchStartY;
          const absX = Math.abs(deltaX);
          const absY = Math.abs(deltaY);

          // Horizontal swipe: threshold 50px
          if (absX > 50 && absX > absY * 1.3) {
            if (deltaX < 0) {
              navigateLightbox(1); // Swipe left -> Next
            } else {
              navigateLightbox(-1); // Swipe right -> Previous
            }
          }
          // Vertical swipe down to close: threshold 80px
          else if (deltaY > 80 && deltaY > absX * 1.4) {
            closeLightbox();
          }
        }
      },
      { passive: true }
    );

    // --- Photo Studio & Editor Events (Fase 6) ---
    if (elements.editorCloseBtn) {
      elements.editorCloseBtn.addEventListener("click", closePhotoEditor);
    }
    if (elements.editorModalBackdrop) {
      elements.editorModalBackdrop.addEventListener("click", closePhotoEditor);
    }
    if (elements.editorResetBtn) {
      elements.editorResetBtn.addEventListener("click", resetEditorState);
    }
    if (elements.editorSaveCopyBtn) {
      elements.editorSaveCopyBtn.addEventListener("click", () => savePhotoEdits(true));
    }
    if (elements.tabTuneBtn) {
      elements.tabTuneBtn.addEventListener("click", () => switchEditorTab("tune"));
    }
    if (elements.tabTransformBtn) {
      elements.tabTransformBtn.addEventListener("click", () => switchEditorTab("transform"));
    }
    if (elements.editorAutoEnhanceBtn) {
      elements.editorAutoEnhanceBtn.addEventListener("click", toggleEditorAutoEnhance);
    }
    if (elements.sliderBrightness) {
      elements.sliderBrightness.addEventListener("input", (e) => {
        state.editState.brightness = parseInt(e.target.value) || 0;
        if (elements.valBrightness) elements.valBrightness.textContent = e.target.value;
        updateEditorPreviewFilters();
      });
    }
    if (elements.sliderContrast) {
      elements.sliderContrast.addEventListener("input", (e) => {
        state.editState.contrast = parseInt(e.target.value) || 0;
        if (elements.valContrast) elements.valContrast.textContent = e.target.value;
        updateEditorPreviewFilters();
      });
    }
    if (elements.sliderSaturation) {
      elements.sliderSaturation.addEventListener("input", (e) => {
        state.editState.saturation = parseInt(e.target.value) || 0;
        if (elements.valSaturation) elements.valSaturation.textContent = e.target.value;
        updateEditorPreviewFilters();
      });
    }
    if (elements.sliderWarmth) {
      elements.sliderWarmth.addEventListener("input", (e) => {
        state.editState.warmth = parseInt(e.target.value) || 0;
        if (elements.valWarmth) elements.valWarmth.textContent = e.target.value;
        updateEditorPreviewFilters();
      });
    }
    if (elements.btnRotate90) {
      elements.btnRotate90.addEventListener("click", () => {
        state.editState.rotate = (state.editState.rotate + 90) % 360;
        updateEditorPreviewFilters();
      });
    }
    if (elements.btnFlipH) {
      elements.btnFlipH.addEventListener("click", () => {
        state.editState.flip_h = !state.editState.flip_h;
        updateEditorPreviewFilters();
      });
    }

    // --- LAN & Mobile QR Code Access Events (Phase 9) ---
    if (elements.lanShareBtn) {
      elements.lanShareBtn.addEventListener("click", openLanModal);
    }
    if (elements.lanModalCloseBtn) {
      elements.lanModalCloseBtn.addEventListener("click", closeLanModal);
    }
    if (elements.lanModalBackdrop) {
      elements.lanModalBackdrop.addEventListener("click", closeLanModal);
    }
    if (elements.lanCopyUrlBtn) {
      elements.lanCopyUrlBtn.addEventListener("click", copyLanUrl);
    }

    // --- Locked Folder & PIN Events (Phase 9) ---
    if (elements.lockedBackBtn) {
      elements.lockedBackBtn.addEventListener("click", () => {
        hideLockedView();
        state.currentCategory = "all";
        document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
        const allChip = document.querySelector('[data-category="all"]');
        if (allChip) allChip.classList.add("active");
        elements.timelineContainer.classList.remove("hidden");
        elements.timelineScrubber.classList.remove("hidden");
        fetchPhotos(true);
      });
    }
    if (elements.lockedRelockBtn) {
      elements.lockedRelockBtn.addEventListener("click", relockFolder);
    }
    if (elements.lockSelectedBtn) {
      elements.lockSelectedBtn.addEventListener("click", () => {
        if (state.currentCategory === "locked") {
          unlockSelectedPhotos();
        } else {
          lockSelectedPhotos();
        }
      });
    }
    if (elements.lightboxLockBtn) {
      elements.lightboxLockBtn.addEventListener("click", lockCurrentLightboxPhoto);
    }
    if (elements.lightboxUnlockBtn) {
      elements.lightboxUnlockBtn.addEventListener("click", unlockCurrentLightboxPhoto);
    }
    if (elements.pinModalCloseBtn) {
      elements.pinModalCloseBtn.addEventListener("click", closePinModal);
    }
    if (elements.pinModalBackdrop) {
      elements.pinModalBackdrop.addEventListener("click", closePinModal);
    }
    if (elements.keypadClearBtn) {
      elements.keypadClearBtn.addEventListener("click", handlePinClear);
    }
    if (elements.keypadBackspaceBtn) {
      elements.keypadBackspaceBtn.addEventListener("click", handlePinBackspace);
    }
    document.querySelectorAll(".keypad-btn[data-key]").forEach((btn) => {
      btn.addEventListener("click", () => handlePinDigit(btn.dataset.key));
    });

    // --- OCR / Live Text Events (Phase 9) ---
    if (elements.lightboxOcrBtn) {
      elements.lightboxOcrBtn.addEventListener("click", triggerPhotoOcr);
    }
    if (elements.ocrModalCloseBtn) {
      elements.ocrModalCloseBtn.addEventListener("click", closeOcrModal);
    }
    if (elements.ocrModalBackdrop) {
      elements.ocrModalBackdrop.addEventListener("click", closeOcrModal);
    }
    if (elements.ocrCopyBtn) {
      elements.ocrCopyBtn.addEventListener("click", copyOcrText);
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
        if (elements.favoriteSelectedBtn) elements.favoriteSelectedBtn.classList.add("hidden");
        if (elements.restoreSelectedBtn) elements.restoreSelectedBtn.classList.remove("hidden");
        if (elements.permanentDeleteSelectedBtn) elements.permanentDeleteSelectedBtn.classList.remove("hidden");
        if (elements.lockSelectedBtn) elements.lockSelectedBtn.classList.add("hidden");
      } else {
        if (elements.addToAlbumBtn) elements.addToAlbumBtn.classList.remove("hidden");
        if (elements.deleteSelectedBtn) elements.deleteSelectedBtn.classList.remove("hidden");
        if (elements.favoriteSelectedBtn) elements.favoriteSelectedBtn.classList.remove("hidden");
        if (elements.restoreSelectedBtn) elements.restoreSelectedBtn.classList.add("hidden");
        if (elements.permanentDeleteSelectedBtn) elements.permanentDeleteSelectedBtn.classList.add("hidden");
        if (elements.lockSelectedBtn) {
          elements.lockSelectedBtn.classList.remove("hidden");
          const span = elements.lockSelectedBtn.querySelector("span");
          if (span) span.textContent = state.currentCategory === "locked" ? "Buka Kunci" : "Kunci";
        }
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

  // --------------------------------------------------------------------------
  // PWA Support (Fase 4)
  // --------------------------------------------------------------------------
  function initPWA() {
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch((err) => {
          console.warn("PWA SW registration notice:", err);
        });
      });
    }
  }

  // --------------------------------------------------------------------------
  // Memories ("Pada Hari Ini" / Flashback - Fase 1)
  // --------------------------------------------------------------------------
  async function loadMemories() {
    if (!elements.memoriesSection || !elements.memoriesCarousel) return;
    try {
      const res = await fetch("/api/memories");
      if (!res.ok) return;
      const data = await res.json();
      state.memories = data.groups || data.memories || [];

      if (state.memories.length === 0) {
        elements.memoriesSection.classList.add("hidden");
        return;
      }

      elements.memoriesCarousel.innerHTML = "";
      state.memories.forEach((mem) => {
        const card = document.createElement("div");
        card.className = "memory-card";
        const coverObj = mem.cover || mem.cover_photo;
        const coverId = coverObj ? coverObj.id : (mem.photos && mem.photos[0] ? mem.photos[0].id : null);
        const coverImgUrl = coverId ? `/api/thumbnails/${coverId}` : "";
        const dateText = mem.date_label || `Tahun ${mem.year}`;

        card.innerHTML = `
          <img src="${coverImgUrl}" alt="${escapeHtml(mem.title)}" loading="lazy" onerror="if(this.src.indexOf('/api/media/')===-1) this.src='/api/media/${coverId}'" />
          <div class="memory-card-overlay">
            <span class="memory-year-badge">${mem.years_ago} TAHUN LALU</span>
            <div class="memory-card-bottom">
              <span class="memory-title-text">${escapeHtml(mem.title)}</span>
              <span class="memory-count-text">${mem.count} foto • ${escapeHtml(dateText)}</span>
            </div>
          </div>
        `;

        card.addEventListener("click", () => {
          if (mem.photos && mem.photos.length > 0) {
            state.photos = [...mem.photos];
            state.lightboxIndex = 0;
            renderLightboxPhoto();
            elements.lightboxModal.classList.remove("hidden");
            document.body.style.overflow = "hidden";
            startSlideshow();
          }
        });

        elements.memoriesCarousel.appendChild(card);
      });

      if (state.currentCategory === "all" && !state.searchQuery && !state.currentYear && !state.currentMonth) {
        elements.memoriesSection.classList.remove("hidden");
      } else {
        elements.memoriesSection.classList.add("hidden");
      }
    } catch (e) {
      console.warn("Memories failed to load", e);
    }
  }

  // --------------------------------------------------------------------------
  // Live Photo & Motion Photo Playback (Fase 3)
  // --------------------------------------------------------------------------
  function toggleLivePhotoPlayback(photo) {
    if (!photo) photo = state.photos[state.lightboxIndex];
    if (!photo || !photo.is_live_photo) return;

    if (state.isLivePhotoPlaying) {
      stopLivePhotoPlayback();
    } else {
      startLivePhotoPlayback(photo);
    }
  }

  function startLivePhotoPlayback(photo) {
    state.isLivePhotoPlaying = true;
    if (elements.lightboxLiveBtn) {
      elements.lightboxLiveBtn.classList.add("playing");
    }
    elements.lightboxImg.classList.add("hidden");
    elements.lightboxVideo.classList.remove("hidden");
    elements.lightboxVideo.src = `/api/media/${photo.id}/motion`;
    elements.lightboxVideo.muted = true;
    elements.lightboxVideo.loop = true;
    elements.lightboxVideo.play().catch((err) => {
      console.warn("Motion video playback notice:", err);
    });
  }

  function stopLivePhotoPlayback() {
    state.isLivePhotoPlaying = false;
    if (elements.lightboxLiveBtn) {
      elements.lightboxLiveBtn.classList.remove("playing");
    }
    const currentPhoto = state.photos[state.lightboxIndex];
    if (currentPhoto && currentPhoto.media_type !== "video") {
      elements.lightboxVideo.pause();
      elements.lightboxVideo.src = "";
      elements.lightboxVideo.classList.add("hidden");
      elements.lightboxImg.classList.remove("hidden");
    }
  }

  // --------------------------------------------------------------------------
  // Duplicates & Storage Cleaner Assistant (Fase 2)
  // --------------------------------------------------------------------------
  async function updateDuplicatesBadge() {
    if (!elements.duplicatesBadgeCount) return;
    try {
      const res = await fetch("/api/duplicates");
      if (!res.ok) return;
      const data = await res.json();
      const groups = data.groups || data.duplicate_groups || [];
      state.duplicateGroups = groups;
      let totalCopies = 0;
      groups.forEach((g) => {
        if (g.photos && g.photos.length > 1) {
          totalCopies += g.photos.length - 1;
        }
      });

      if (totalCopies > 0) {
        elements.duplicatesBadgeCount.textContent = totalCopies;
        elements.duplicatesBadgeCount.classList.remove("hidden");
      } else {
        elements.duplicatesBadgeCount.classList.add("hidden");
      }
    } catch (e) {
      console.warn("Failed to check duplicates count", e);
    }
  }

  async function showDuplicatesView() {
    state.currentCategory = "duplicates";
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.add("hidden");
    elements.trashContainer.classList.add("hidden");
    elements.mapContainer.classList.add("hidden");
    elements.filterBanner.classList.add("hidden");
    elements.duplicatesContainer.classList.remove("hidden");

    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    if (elements.duplicatesChip) elements.duplicatesChip.classList.add("active");

    await loadDuplicates();
  }

  function hideDuplicatesView() {
    elements.duplicatesContainer.classList.add("hidden");
    state.selectedDuplicates.clear();
    updateDuplicatesSelectedUI();
  }

  async function loadDuplicates() {
    elements.duplicatesGroupsList.innerHTML = '<div class="spinner-small" style="margin: 40px auto;"></div>';
    elements.duplicatesSummaryBadge.textContent = "Mendeteksi...";
    state.selectedDuplicates.clear();
    updateDuplicatesSelectedUI();

    try {
      const res = await fetch("/api/duplicates");
      const data = await res.json();
      const groups = data.groups || data.duplicate_groups || [];
      state.duplicateGroups = groups;

      let totalCopies = 0;
      let totalSavableBytes = 0;
      groups.forEach((g) => {
        if (g.photos && g.photos.length > 1) {
          totalCopies += g.photos.length - 1;
          totalSavableBytes += (g.savable_bytes || g.potential_savings_bytes || 0);
        }
      });

      if (groups.length === 0) {
        elements.duplicatesGroupsList.innerHTML = "";
        elements.duplicatesEmptyState.classList.remove("hidden");
        elements.duplicatesSummaryBadge.textContent = "0 Duplikat";
        elements.duplicatesBadgeCount.classList.add("hidden");
        elements.duplicatesAutoSelectBtn.disabled = true;
        elements.duplicatesDeleteSelectedBtn.disabled = true;
        return;
      }

      elements.duplicatesEmptyState.classList.add("hidden");
      elements.duplicatesAutoSelectBtn.disabled = false;
      elements.duplicatesDeleteSelectedBtn.disabled = false;
      elements.duplicatesSummaryBadge.textContent = `${groups.length} Grup (${totalCopies} duplikat • Hemat ${formatBytes(totalSavableBytes)})`;
      if (elements.duplicatesBadgeCount) {
        elements.duplicatesBadgeCount.textContent = totalCopies;
        elements.duplicatesBadgeCount.classList.remove("hidden");
      }

      elements.duplicatesGroupsList.innerHTML = "";
      groups.forEach((group, gIdx) => {
        const groupCard = document.createElement("div");
        groupCard.className = "duplicate-group-card";

        const isExact = (group.type === "exact_duplicate" || group.group_type === "exact_duplicate");
        const badgeClass = isExact ? "dup-group-badge" : "dup-group-badge near_duplicate";
        const badgeText = isExact ? "100% IDENTIK" : "FOTO SERUPA / BURST";
        const savableGroupBytes = group.savable_bytes || group.potential_savings_bytes || 0;

        groupCard.innerHTML = `
          <div class="dup-group-header">
            <div class="dup-group-meta">
              <span class="${badgeClass}">${badgeText}</span>
              <span class="dup-group-reason">${escapeHtml(group.reason)}</span>
            </div>
            <span class="dup-savings-badge">Hemat ${formatBytes(savableGroupBytes)}</span>
          </div>
          <div class="dup-photos-grid" id="dupGroupGrid_${gIdx}"></div>
        `;

        const grid = groupCard.querySelector(`#dupGroupGrid_${gIdx}`);
        group.photos.forEach((photo, pIdx) => {
          const isBest = pIdx === 0;
          const photoCard = document.createElement("div");
          photoCard.className = `dup-photo-card ${isBest ? "recommended-keep" : ""}`;
          photoCard.setAttribute("data-photo-id", photo.id);

          photoCard.innerHTML = `
            <div class="dup-photo-thumb-wrap">
              <span class="dup-tag-pill ${isBest ? "best" : "copy"}">${isBest ? "BEST" : "COPY"}</span>
              <div class="dup-checkbox-wrap">
                <input type="checkbox" class="dup-check" data-id="${photo.id}" ${isBest ? "disabled" : ""} />
              </div>
              <img src="/api/thumbnails/${photo.id}" loading="lazy" alt="${escapeHtml(photo.filename)}" onerror="this.src='/api/media/${photo.id}'" />
            </div>
            <div class="dup-photo-info">
              <span class="dup-filename" title="${escapeHtml(photo.filename)}">${escapeHtml(photo.filename)}</span>
              <span class="dup-dimensions">${photo.width || "?"}×${photo.height || "?"} • ${formatBytes(photo.file_size)}</span>
            </div>
          `;

          const imgWrap = photoCard.querySelector(".dup-photo-thumb-wrap img");
          imgWrap.addEventListener("click", () => {
            state.photos = group.photos;
            openLightbox(photo.id);
          });

          const checkbox = photoCard.querySelector(".dup-check");
          if (!isBest) {
            checkbox.addEventListener("change", (e) => {
              if (e.target.checked) {
                state.selectedDuplicates.add(photo.id);
                photoCard.classList.add("selected");
              } else {
                state.selectedDuplicates.delete(photo.id);
                photoCard.classList.remove("selected");
              }
              updateDuplicatesSelectedUI();
            });
          }

          grid.appendChild(photoCard);
        });

        elements.duplicatesGroupsList.appendChild(groupCard);
      });
    } catch (e) {
      console.error("Gagal memuat duplikat", e);
      elements.duplicatesGroupsList.innerHTML = '<div class="empty-state">Gagal memuat duplikat.</div>';
    }
  }

  function updateDuplicatesSelectedUI() {
    const count = state.selectedDuplicates.size;
    if (elements.duplicatesSelectedCount) {
      elements.duplicatesSelectedCount.textContent = count;
    }
    if (elements.duplicatesDeleteSelectedBtn) {
      elements.duplicatesDeleteSelectedBtn.disabled = count === 0;
    }
  }

  function autoSelectDuplicates() {
    state.selectedDuplicates.clear();
    const checkboxes = elements.duplicatesGroupsList.querySelectorAll(".dup-check:not([disabled])");
    checkboxes.forEach((cb) => {
      cb.checked = true;
      const id = parseInt(cb.dataset.id, 10);
      state.selectedDuplicates.add(id);
      const card = cb.closest(".dup-photo-card");
      if (card) card.classList.add("selected");
    });
    updateDuplicatesSelectedUI();
    showToast(`${state.selectedDuplicates.size} foto duplikat dipilih otomatis (foto BEST dipertahankan).`);
  }

  async function deleteSelectedDuplicates() {
    if (state.selectedDuplicates.size === 0) return;
    const ids = Array.from(state.selectedDuplicates);
    const count = ids.length;

    try {
      const res = await fetch("/api/duplicates/cleanup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids }),
      });

      if (res.ok) {
        showToast(`${count} foto duplikat dipindahkan ke Tempat Sampah 🗑️`);
        state.selectedDuplicates.clear();
        updateDuplicatesSelectedUI();
        updateTrashBadge();
        loadDuplicates();
      } else {
        showToast("Gagal memindahkan duplikat ke tempat sampah", null, null, 3000);
      }
    } catch (e) {
      console.error("Error cleaning duplicates", e);
      showToast("Terjadi kesalahan saat membersihkan duplikat", null, null, 3000);
    }
  }

  async function showTrashView() {
    state.currentCategory = "trash";
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.add("hidden");
    elements.duplicatesContainer.classList.add("hidden");
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
    elements.duplicatesContainer.classList.add("hidden");
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
    elements.duplicatesContainer.classList.add("hidden");
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

  // ==============================================================================
  // Photo Editor Suite (Fase 6)
  // ==============================================================================
  function openPhotoEditor(photo = null) {
    const targetPhoto = photo || state.photos[state.lightboxIndex];
    if (!targetPhoto) return;

    if (targetPhoto.media_type === "video") {
      showToast("Hanya file foto/gambar yang dapat diedit di studio.", null, null, 2500);
      return;
    }

    if (state.isSlideshowPlaying) {
      stopSlideshow();
    }

    state.editingPhoto = targetPhoto;
    if (elements.editorFilename) {
      elements.editorFilename.textContent = targetPhoto.filename || "Photo";
    }

    resetEditorState();

    if (elements.editorPreviewImg) {
      elements.editorPreviewImg.src = `/api/media/${targetPhoto.id}`;
    }

    switchEditorTab("tune");

    if (elements.editorModalWrapper) {
      elements.editorModalWrapper.classList.remove("hidden");
    }
  }

  function closePhotoEditor() {
    if (elements.editorModalWrapper) {
      elements.editorModalWrapper.classList.add("hidden");
    }
    state.editingPhoto = null;
  }

  function switchEditorTab(tab) {
    if (tab === "tune") {
      if (elements.tabTuneBtn) elements.tabTuneBtn.classList.add("active");
      if (elements.tabTransformBtn) elements.tabTransformBtn.classList.remove("active");
      if (elements.panelTune) elements.panelTune.classList.remove("hidden");
      if (elements.panelTransform) elements.panelTransform.classList.add("hidden");
    } else {
      if (elements.tabTransformBtn) elements.tabTransformBtn.classList.add("active");
      if (elements.tabTuneBtn) elements.tabTuneBtn.classList.remove("active");
      if (elements.panelTransform) elements.panelTransform.classList.remove("hidden");
      if (elements.panelTune) elements.panelTune.classList.add("hidden");
    }
  }

  function toggleEditorAutoEnhance() {
    state.editState.auto_enhance = !state.editState.auto_enhance;
    if (elements.editorAutoEnhanceBtn) {
      elements.editorAutoEnhanceBtn.classList.toggle("active", state.editState.auto_enhance);
    }
    updateEditorPreviewFilters();
  }

  function updateEditorPreviewFilters() {
    if (!elements.editorPreviewImg) return;

    const b = 1 + (state.editState.brightness / 100);
    const c = 1 + (state.editState.contrast / 100);
    const s = 1 + (state.editState.saturation / 100);

    const w = state.editState.warmth;
    let sepia = 0;
    let hue = 0;
    if (w > 0) {
      sepia = (w / 100) * 0.35;
      hue = (w / 100) * -10;
    } else if (w < 0) {
      hue = (Math.abs(w) / 100) * 15;
    }

    let filterStr = `brightness(${b}) contrast(${c}) saturate(${s})`;
    if (sepia > 0) filterStr += ` sepia(${sepia})`;
    if (hue !== 0) filterStr += ` hue-rotate(${hue}deg)`;
    if (state.editState.auto_enhance) {
      filterStr += " contrast(1.1) saturate(1.15)";
    }

    elements.editorPreviewImg.style.filter = filterStr;

    const rot = state.editState.rotate % 360;
    const scaleX = state.editState.flip_h ? -1 : 1;
    elements.editorPreviewImg.style.transform = `rotate(${rot}deg) scaleX(${scaleX})`;
  }

  function resetEditorState() {
    state.editState = {
      rotate: 0,
      flip_h: false,
      brightness: 0,
      contrast: 0,
      saturation: 0,
      warmth: 0,
      auto_enhance: false,
    };

    if (elements.sliderBrightness) elements.sliderBrightness.value = 0;
    if (elements.sliderContrast) elements.sliderContrast.value = 0;
    if (elements.sliderSaturation) elements.sliderSaturation.value = 0;
    if (elements.sliderWarmth) elements.sliderWarmth.value = 0;

    if (elements.valBrightness) elements.valBrightness.textContent = "0";
    if (elements.valContrast) elements.valContrast.textContent = "0";
    if (elements.valSaturation) elements.valSaturation.textContent = "0";
    if (elements.valWarmth) elements.valWarmth.textContent = "0";

    if (elements.editorAutoEnhanceBtn) {
      elements.editorAutoEnhanceBtn.classList.remove("active");
    }

    updateEditorPreviewFilters();
  }

  async function savePhotoEdits(saveAsCopy = true) {
    if (!state.editingPhoto) return;
    const photo = state.editingPhoto;

    const originalBtnText = elements.editorSaveCopyBtn ? elements.editorSaveCopyBtn.textContent : "Simpan";
    if (elements.editorSaveCopyBtn) {
      elements.editorSaveCopyBtn.disabled = true;
      elements.editorSaveCopyBtn.textContent = "Menyimpan...";
    }

    try {
      const payload = {
        crop: null,
        rotate: state.editState.rotate,
        flip_h: state.editState.flip_h,
        brightness: state.editState.brightness,
        contrast: state.editState.contrast,
        saturation: state.editState.saturation,
        warmth: state.editState.warmth,
        auto_enhance: state.editState.auto_enhance,
        save_as_copy: saveAsCopy,
      };

      const res = await fetch(`/api/photos/${photo.id}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Gagal menyimpan editan foto");
      }

      const result = await res.json();
      closePhotoEditor();

      showToast(
        saveAsCopy
          ? `Salinan baru tersimpan: ${result.filename} ✨`
          : "Perubahan foto berhasil disimpan!",
        null,
        null,
        3500
      );

      // Refresh photo gallery timeline
      fetchPhotos(true);

      // If lightbox is currently showing this photo and overwritten
      if (!saveAsCopy && elements.lightboxImg && state.photos[state.lightboxIndex]?.id === photo.id) {
        elements.lightboxImg.src = `/api/media/${photo.id}?t=${Date.now()}`;
      }
    } catch (e) {
      console.error("Save edits error:", e);
      showToast(`Error: ${e.message}`, null, null, 4000);
    } finally {
      if (elements.editorSaveCopyBtn) {
        elements.editorSaveCopyBtn.disabled = false;
        elements.editorSaveCopyBtn.textContent = originalBtnText;
      }
    }
  }

  // --------------------------------------------------------------------------
  // Phase 9: Home Wi-Fi LAN & Mobile Access
  // --------------------------------------------------------------------------
  async function openLanModal() {
    if (!elements.lanModalWrapper) return;
    elements.lanModalWrapper.classList.remove("hidden");
    elements.lanQrContainer.innerHTML = '<div class="spinner-small" style="margin: auto;"></div>';
    elements.lanUrlInput.value = "Memuat...";

    try {
      const res = await fetch("/api/system/network");
      if (!res.ok) throw new Error("Gagal mengambil info jaringan");
      const data = await res.json();
      
      elements.lanUrlInput.value = data.lan_url;
      elements.lanQrContainer.innerHTML = data.qr_code_svg;
    } catch (e) {
      console.error("Error fetching network info", e);
      elements.lanQrContainer.innerHTML = '<span style="color:#ea4335; font-size:0.8rem;">Gagal membuat kode QR</span>';
      elements.lanUrlInput.value = window.location.origin;
    }
  }

  function closeLanModal() {
    if (elements.lanModalWrapper) {
      elements.lanModalWrapper.classList.add("hidden");
    }
  }

  function copyLanUrl() {
    if (!elements.lanUrlInput) return;
    elements.lanUrlInput.select();
    navigator.clipboard.writeText(elements.lanUrlInput.value)
      .then(() => showToast("URL lokal berhasil disalin ke clipboard! 📋"))
      .catch(() => showToast("Gagal menyalin URL"));
  }

  // --------------------------------------------------------------------------
  // Phase 9: Locked Folder & PIN Keypad Security
  // --------------------------------------------------------------------------
  async function updateLockedBadge() {
    try {
      const res = await fetch("/api/locked/status");
      if (!res.ok) return;
      const data = await res.json();
      const count = data.locked_count || 0;
      if (elements.lockedBadgeCount) {
        elements.lockedBadgeCount.textContent = count;
        elements.lockedBadgeCount.classList.toggle("hidden", count === 0);
      }
      if (elements.lockedCountBadge) {
        elements.lockedCountBadge.textContent = `${count} item`;
      }
    } catch (e) {
      console.warn("Failed to check locked status", e);
    }
  }

  async function openLockedFolderWithPin() {
    if (state.lockedToken) {
      showLockedView();
      return;
    }

    try {
      const res = await fetch("/api/locked/status");
      const data = await res.json();

      state.isPinSetupMode = !data.has_pin;
      state.pinSetupFirstPass = "";
      state.lockedPinInput = "";
      updatePinDotsUI();

      if (state.isPinSetupMode) {
        elements.pinModalTitle.textContent = "Buat PIN Baru";
        elements.pinModalSubtitle.textContent = "Tentukan 4-digit PIN untuk Folder Terkunci Anda";
      } else {
        elements.pinModalTitle.textContent = "Buka Folder Terkunci";
        elements.pinModalSubtitle.textContent = "Masukkan 4-digit PIN keamanan Anda";
      }

      elements.pinErrorText.classList.add("hidden");
      elements.pinModalWrapper.classList.remove("hidden");
    } catch (e) {
      console.error("Error opening locked folder", e);
      showToast("Gagal memeriksa status PIN");
    }
  }

  function closePinModal() {
    if (elements.pinModalWrapper) {
      elements.pinModalWrapper.classList.add("hidden");
    }
    state.lockedPinInput = "";
    state.pinSetupFirstPass = "";
    updatePinDotsUI();

    if (state.currentCategory === "locked" && !state.lockedToken) {
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      const allChip = document.querySelector('[data-category="all"]');
      if (allChip) allChip.classList.add("active");
      state.currentCategory = "all";
      fetchPhotos(true);
    }
  }

  function updatePinDotsUI() {
    const len = state.lockedPinInput.length;
    for (let i = 0; i < 4; i++) {
      const dot = document.getElementById(`pinDot${i}`);
      if (dot) {
        dot.classList.toggle("filled", i < len);
      }
    }
  }

  async function handlePinDigit(digit) {
    if (state.lockedPinInput.length >= 4) return;
    state.lockedPinInput += digit;
    updatePinDotsUI();
    elements.pinErrorText.classList.add("hidden");

    if (state.lockedPinInput.length === 4) {
      await processCompletedPin();
    }
  }

  function handlePinBackspace() {
    if (state.lockedPinInput.length > 0) {
      state.lockedPinInput = state.lockedPinInput.slice(0, -1);
      updatePinDotsUI();
    }
  }

  function handlePinClear() {
    state.lockedPinInput = "";
    updatePinDotsUI();
  }

  async function processCompletedPin() {
    const enteredPin = state.lockedPinInput;

    if (state.isPinSetupMode) {
      if (!state.pinSetupFirstPass) {
        state.pinSetupFirstPass = enteredPin;
        state.lockedPinInput = "";
        updatePinDotsUI();
        elements.pinModalTitle.textContent = "Konfirmasi PIN";
        elements.pinModalSubtitle.textContent = "Masukkan 4-digit PIN sekali lagi";
        return;
      }

      if (enteredPin !== state.pinSetupFirstPass) {
        elements.pinErrorText.textContent = "PIN tidak cocok. Ulangi pembuatan PIN.";
        elements.pinErrorText.classList.remove("hidden");
        state.pinSetupFirstPass = "";
        state.lockedPinInput = "";
        updatePinDotsUI();
        elements.pinModalTitle.textContent = "Buat PIN Baru";
        elements.pinModalSubtitle.textContent = "Tentukan 4-digit PIN untuk Folder Terkunci Anda";
        return;
      }

      try {
        const res = await fetch("/api/locked/setup-pin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin: enteredPin })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          showToast("PIN keamanan berhasil dibuat! 🔒");
          const vRes = await fetch("/api/locked/verify-pin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pin: enteredPin })
          });
          const vData = await vRes.json();
          if (vRes.ok && vData.token) {
            state.lockedToken = vData.token;
            elements.pinModalWrapper.classList.add("hidden");
            showLockedView();
          }
        } else {
          elements.pinErrorText.textContent = data.detail || "Gagal membuat PIN";
          elements.pinErrorText.classList.remove("hidden");
        }
      } catch (e) {
        elements.pinErrorText.textContent = "Terjadi kesalahan";
        elements.pinErrorText.classList.remove("hidden");
      }
      return;
    }

    try {
      const res = await fetch("/api/locked/verify-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: enteredPin })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        state.lockedToken = data.token;
        elements.pinModalWrapper.classList.add("hidden");
        showLockedView();
      } else {
        elements.pinErrorText.textContent = "PIN salah. Silakan coba lagi.";
        elements.pinErrorText.classList.remove("hidden");
        state.lockedPinInput = "";
        updatePinDotsUI();
      }
    } catch (e) {
      elements.pinErrorText.textContent = "Gagal memverifikasi PIN";
      elements.pinErrorText.classList.remove("hidden");
      state.lockedPinInput = "";
      updatePinDotsUI();
    }
  }

  async function showLockedView() {
    state.currentCategory = "locked";
    elements.timelineContainer.classList.add("hidden");
    elements.timelineScrubber.classList.add("hidden");
    elements.albumContainer.classList.add("hidden");
    elements.trashContainer.classList.add("hidden");
    elements.duplicatesContainer.classList.add("hidden");
    elements.filterBanner.classList.add("hidden");
    elements.lockedContainer.classList.remove("hidden");

    clearSelection();
    elements.lockedGrid.innerHTML = '<div class="spinner-small" style="margin: 40px auto; grid-column: 1 / -1;"></div>';

    try {
      const res = await fetch(`/api/locked/photos?token=${encodeURIComponent(state.lockedToken || "")}`);
      if (!res.ok) {
        if (res.status === 401) {
          state.lockedToken = null;
          showToast("Sesi PIN berakhir. Masukkan PIN kembali.");
          openLockedFolderWithPin();
          return;
        }
        throw new Error("Gagal memuat item terkunci");
      }

      const data = await res.json();
      const photos = data.photos || [];
      state.photos = photos;

      updateLockedBadge();

      if (photos.length === 0) {
        elements.lockedGrid.innerHTML = "";
        elements.lockedEmptyState.classList.remove("hidden");
      } else {
        elements.lockedEmptyState.classList.add("hidden");
        elements.lockedGrid.innerHTML = "";
        photos.forEach((photo) => {
          elements.lockedGrid.appendChild(createPhotoTile(photo));
        });
      }
    } catch (e) {
      console.error("Failed to load locked photos", e);
      elements.lockedGrid.innerHTML = '<div class="empty-state" style="grid-column: 1 / -1;">Error loading locked folder</div>';
    }
  }

  function hideLockedView() {
    if (elements.lockedContainer) {
      elements.lockedContainer.classList.add("hidden");
    }
  }

  function relockFolder() {
    state.lockedToken = null;
    showToast("Folder Terkunci telah dikunci kembali 🔒");
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    const allChip = document.querySelector('[data-category="all"]');
    if (allChip) allChip.classList.add("active");
    state.currentCategory = "all";
    hideLockedView();
    fetchPhotos(true);
  }

  async function lockSelectedPhotos() {
    if (state.selectedPhotos.size === 0) return;
    const ids = Array.from(state.selectedPhotos);
    const count = ids.length;

    try {
      const res = await fetch("/api/photos/lock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        ids.forEach((id) => {
          const tile = document.querySelector(`.photo-tile[data-id="${id}"]`);
          if (tile) tile.remove();
        });
        state.photos = state.photos.filter((p) => !ids.includes(p.id));
        clearSelection();
        loadTimelineHierarchy();
        updateLockedBadge();
        showToast(`${count} foto disembunyikan ke Folder Terkunci 🔒`);
      } else {
        showToast("Gagal mengunci foto", null, null, 3000);
      }
    } catch (e) {
      console.error("Error locking photos", e);
      showToast("Terjadi kesalahan saat mengunci foto");
    }
  }

  async function unlockSelectedPhotos(photoIds) {
    const ids = photoIds || (state.selectedPhotos.size > 0 ? Array.from(state.selectedPhotos) : []);
    if (ids.length === 0) return;

    try {
      const res = await fetch("/api/photos/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids, token: state.lockedToken || "" })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`${ids.length} foto dikeluarkan dari Folder Terkunci ke galeri ✨`);
        clearSelection();
        updateLockedBadge();
        loadTimelineHierarchy();
        if (state.currentCategory === "locked") {
          await showLockedView();
        } else {
          await fetchPhotos(true);
        }
      } else {
        showToast("Gagal mengeluarkan foto");
      }
    } catch (e) {
      console.error("Error unlocking photos", e);
      showToast("Terjadi kesalahan saat membuka kunci");
    }
  }

  async function lockCurrentLightboxPhoto() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];
    await lockSelectedPhotosByIds([photo.id]);
    closeLightbox();
  }

  async function unlockCurrentLightboxPhoto() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];
    await unlockSelectedPhotos([photo.id]);
    closeLightbox();
  }

  async function lockSelectedPhotosByIds(ids) {
    try {
      const res = await fetch("/api/photos/lock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_ids: ids })
      });
      if (res.ok) {
        showToast(`${ids.length} foto disembunyikan ke Folder Terkunci 🔒`);
        updateLockedBadge();
        loadTimelineHierarchy();
        fetchPhotos(true);
      }
    } catch (e) {}
  }

  // --------------------------------------------------------------------------
  // Phase 9: Live Text / OCR Engine
  // --------------------------------------------------------------------------
  async function triggerPhotoOcr() {
    if (state.lightboxIndex === -1 || !state.photos[state.lightboxIndex]) return;
    const photo = state.photos[state.lightboxIndex];

    elements.ocrModalWrapper.classList.remove("hidden");
    elements.ocrLoadingState.classList.remove("hidden");
    elements.ocrTextContainer.classList.add("hidden");
    elements.ocrTextarea.value = "";
    elements.ocrCharCount.textContent = "0 karakter";

    try {
      const res = await fetch(`/api/photos/${photo.id}/ocr`, { method: "POST" });
      const data = await res.json();
      
      elements.ocrLoadingState.classList.add("hidden");
      elements.ocrTextContainer.classList.remove("hidden");

      const text = (data.ocr_text || "").trim();
      elements.ocrTextarea.value = text;
      elements.ocrCharCount.textContent = `${text.length} karakter terdeteksi`;

      if (!text) {
        elements.ocrTextarea.placeholder = "Tidak ada teks yang terdeteksi pada foto ini.";
      }
    } catch (e) {
      console.error("OCR trigger error", e);
      elements.ocrLoadingState.classList.add("hidden");
      elements.ocrTextContainer.classList.remove("hidden");
      elements.ocrTextarea.value = "";
      elements.ocrTextarea.placeholder = "Gagal memproses OCR pada gambar.";
      showToast("Gagal mengekstrak teks");
    }
  }

  function closeOcrModal() {
    if (elements.ocrModalWrapper) {
      elements.ocrModalWrapper.classList.add("hidden");
    }
  }

  function copyOcrText() {
    if (!elements.ocrTextarea) return;
    const text = elements.ocrTextarea.value.trim();
    if (!text) {
      showToast("Tidak ada teks untuk disalin");
      return;
    }
    navigator.clipboard.writeText(text)
      .then(() => showToast("Teks OCR berhasil disalin! 📝"))
      .catch(() => showToast("Gagal menyalin teks"));
  }

  // --- Bootstrap ---
  init();
})();
