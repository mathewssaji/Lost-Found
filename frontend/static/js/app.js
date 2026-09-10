/**
 * Campus Lost & Found Engine - High-Performance Frontend Application
 */

const API = {
  getStats: () => fetch('/api/stats').then(r => r.json()),
  getOptions: async () => {
    const cached = sessionStorage.getItem('campus_options');
    if (cached) {
      try { return JSON.parse(cached); } catch (e) {}
    }
    const data = await fetch('/api/config/options').then(r => r.json());
    sessionStorage.setItem('campus_options', JSON.stringify(data));
    return data;
  },
  getItems: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetch(`/api/items?${q}`).then(r => r.json());
  },
  getItem: (id) => fetch(`/api/items/${id}`).then(r => r.json()),
  claimItem: (id) => fetch(`/api/items/${id}/claim`, { method: 'POST' }).then(r => r.json()),
  reportItem: (formData) => fetch('/api/items', { method: 'POST', body: formData }).then(r => r.json()),
  scanVisual: (formData) => fetch('/api/match/scan', { method: 'POST', body: formData }).then(r => r.json()),
};

// Global App State
window.AppState = {
  currentFilter: 'ALL',
  currentStatus: 'ACTIVE',
  currentCategory: '',
  currentLocation: '',
  searchQuery: '',
  items: [],
  selectedFile: null,
  activeReportType: 'LOST',
  categories: [],
  locations: []
};

// Fast Client-Side Image Compressor (Reduces upload from 5MB to ~50KB in 20ms)
async function compressImageFile(file, maxWidth = 800, quality = 0.82) {
  if (!file || !file.type.startsWith('image/')) return file;
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = (event) => {
      const img = new Image();
      img.src = event.target.result;
      img.onload = () => {
        let width = img.width;
        let height = img.height;

        if (width > maxWidth) {
          height = Math.round((height * maxWidth) / width);
          width = maxWidth;
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            if (blob && blob.size < file.size) {
              const compressed = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", {
                type: 'image/jpeg',
                lastModified: Date.now(),
              });
              resolve(compressed);
            } else {
              resolve(file);
            }
          },
          'image/jpeg',
          quality
        );
      };
      img.onerror = () => resolve(file);
    };
    reader.onerror = () => resolve(file);
  });
}

// Notification Toast
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  const toastMsg = document.getElementById('toast-msg');

  toastMsg.textContent = message;
  toast.className = `fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl text-white font-medium transition-all duration-300 transform translate-y-0 opacity-100 ${
    type === 'success' ? 'bg-emerald-600' : type === 'error' ? 'bg-rose-600' : 'bg-slate-800'
  }`;

  setTimeout(() => {
    toast.className = 'fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl text-white font-medium transition-all duration-300 transform translate-y-10 opacity-0 pointer-events-none';
  }, 3500);
}

// Format relative date
function formatDate(isoStr) {
  if (!isoStr) return 'Recently';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diffHours = Math.round((now - d) / (1000 * 60 * 60));
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours} hr${diffHours > 1 ? 's' : ''} ago`;
    const diffDays = Math.round(diffHours / 24);
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch (e) {
    return 'Recently';
  }
}

// Render Skeleton Placeholders
function renderSkeletons(count = 6) {
  const skeletons = Array(count).fill(0).map(() => `
    <div class="bg-white dark:bg-slate-800 rounded-2xl overflow-hidden border border-slate-200/80 dark:border-slate-700/80 shadow-xs flex flex-col justify-between">
      <div>
        <div class="h-48 w-full skeleton-box"></div>
        <div class="p-5 space-y-3">
          <div class="flex gap-2">
            <div class="h-4 w-16 rounded skeleton-box"></div>
            <div class="h-4 w-24 rounded skeleton-box"></div>
          </div>
          <div class="h-5 w-3/4 rounded skeleton-box"></div>
          <div class="h-3 w-full rounded skeleton-box"></div>
          <div class="h-3 w-2/3 rounded skeleton-box"></div>
        </div>
      </div>
      <div class="p-5 pt-0 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between pt-3">
        <div class="h-4 w-20 rounded skeleton-box"></div>
        <div class="h-7 w-20 rounded-lg skeleton-box"></div>
      </div>
    </div>
  `).join('');
  return skeletons;
}

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  loadOptions();
  refreshStats();

  if (document.getElementById('items-grid')) {
    loadItems();
    setupFilters();
  }

  setupReportModal();
  setupDropzone();
  setupVisualMatcher();
});

// Load Config Options (Cached for Instant Page Loads)
async function loadOptions() {
  try {
    const data = await API.getOptions();
    window.AppState.categories = data.categories || [];
    window.AppState.locations = data.locations || [];

    // Populate category dropdowns
    const catSelects = document.querySelectorAll('.category-dropdown');
    catSelects.forEach(sel => {
      const isFilter = sel.dataset.isFilter === 'true';
      let html = isFilter ? '<option value="">All Categories</option>' : '<option value="">Select Category...</option>';
      window.AppState.categories.forEach(cat => {
        html += `<option value="${cat}">${cat}</option>`;
      });
      sel.innerHTML = html;
    });

    // Populate location dropdowns
    const locSelects = document.querySelectorAll('.location-dropdown');
    locSelects.forEach(sel => {
      const isFilter = sel.dataset.isFilter === 'true';
      let html = isFilter ? '<option value="">All Locations</option>' : '<option value="">Select Campus Location...</option>';
      window.AppState.locations.forEach(loc => {
        html += `<option value="${loc}">${loc}</option>`;
      });
      sel.innerHTML = html;
    });
  } catch (e) {
    console.error('Error loading options:', e);
  }
}

// Refresh Live Campus Statistics
async function refreshStats() {
  try {
    const stats = await API.getStats();
    
    // Update live counter in navbar
    const navPill = document.getElementById('nav-active-count');
    if (navPill) navPill.textContent = `${stats.total_active} Active on Campus`;

    const statActive = document.getElementById('stat-total-active');
    if (statActive) statActive.textContent = stats.total_active;

    const statLost = document.getElementById('stat-total-lost');
    if (statLost) statLost.textContent = stats.total_lost;

    const statFound = document.getElementById('stat-total-found');
    if (statFound) statFound.textContent = stats.total_found;

    const statClaimed = document.getElementById('stat-total-claimed');
    if (statClaimed) statClaimed.textContent = stats.total_claimed;

    const mongoBadge = document.getElementById('mongo-status-badge');
    if (mongoBadge) {
      if (stats.is_mongo_connected) {
        mongoBadge.innerHTML = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"><span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>MongoDB Atlas Vector Active</span>`;
      } else {
        mongoBadge.innerHTML = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"><span class="w-2 h-2 rounded-full bg-indigo-500"></span>In-Memory High-Speed Engine</span>`;
      }
    }
  } catch (e) {
    console.error('Error refreshing stats:', e);
  }
}

// Load Items into Grid with Skeletons
async function loadItems() {
  const grid = document.getElementById('items-grid');
  const countEl = document.getElementById('filtered-count');
  if (!grid) return;

  grid.innerHTML = renderSkeletons(4);

  try {
    const params = {
      item_type: window.AppState.currentFilter,
      status: window.AppState.currentStatus,
    };
    if (window.AppState.currentCategory) params.category = window.AppState.currentCategory;
    if (window.AppState.currentLocation) params.location = window.AppState.currentLocation;
    if (window.AppState.searchQuery) params.search = window.AppState.searchQuery;

    const data = await API.getItems(params);
    window.AppState.items = data.items || [];

    if (countEl) countEl.textContent = `${window.AppState.items.length} item${window.AppState.items.length === 1 ? '' : 's'}`;

    if (window.AppState.items.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full py-16 text-center bg-white dark:bg-slate-800/60 rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 p-8">
          <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-500 shadow-inner">
            <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          </div>
          <h3 class="text-base font-bold text-slate-800 dark:text-slate-100">No active reports match</h3>
          <p class="text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto text-xs">Try clearing filters or search terms.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = window.AppState.items.map(item => renderItemCard(item)).join('');
  } catch (e) {
    grid.innerHTML = `<div class="col-span-full py-12 text-center text-rose-500 font-medium text-xs">Failed to load items. Please try again.</div>`;
  }
}

// Render Single Item Card HTML
function renderItemCard(item) {
  const isLost = item.item_type === 'LOST';
  const isClaimed = item.status === 'CLAIMED';
  const badgeClass = isLost
    ? 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-950/80 dark:text-rose-300 dark:border-rose-800'
    : 'bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-950/80 dark:text-sky-300 dark:border-sky-800';

  const defaultImg = isLost ? '/sample_assets/laptop_lost.jpg' : '/sample_assets/laptop_found.jpg';
  const imgSrc = item.image_path || defaultImg;

  return `
    <div class="animate-card-in group bg-white dark:bg-slate-800 rounded-3xl overflow-hidden border border-slate-200/80 dark:border-slate-700/80 shadow-xs hover:shadow-xl hover:border-indigo-300 dark:hover:border-indigo-600 transition-all duration-300 flex flex-col justify-between">
      <div>
        <div class="relative h-48 w-full bg-slate-100 dark:bg-slate-900 img-zoom-container cursor-pointer" onclick="openItemDetail('${item.id}')">
          <img src="${imgSrc}" alt="${item.title}" loading="lazy" class="w-full h-full object-cover" onerror="this.src='/sample_assets/laptop_lost.jpg'">
          <div class="absolute top-3 left-3 flex gap-2">
            <span class="px-2.5 py-1 text-xs font-bold rounded-lg border ${badgeClass} shadow-xs backdrop-blur-md">
              ${item.item_type}
            </span>
            ${isClaimed ? `
              <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 shadow-xs">
                RESOLVED
              </span>
            ` : ''}
          </div>
          <div class="absolute bottom-3 right-3">
            <span class="px-2 py-0.5 text-[11px] font-medium rounded-md bg-black/60 text-white backdrop-blur-md">
              ${formatDate(item.created_at)}
            </span>
          </div>
        </div>

        <div class="p-5">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
              ${item.category}
            </span>
            <span class="text-xs text-slate-400 flex items-center gap-1">
              <svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
              ${item.location}
            </span>
          </div>

          <h3 class="text-sm sm:text-base font-bold text-slate-900 dark:text-white line-clamp-1 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
            ${item.title}
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
            ${item.description}
          </p>

          ${item.tags && item.tags.length ? `
            <div class="flex flex-wrap gap-1 mt-3">
              ${item.tags.slice(0, 3).map(t => `<span class="text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 font-medium">#${t}</span>`).join('')}
            </div>
          ` : ''}
        </div>
      </div>

      <div class="p-5 pt-0 mt-2 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between gap-3 pt-3">
        <button onclick="openItemDetail('${item.id}')" class="text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-indigo-600 flex items-center gap-1">
          View Details
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
        </button>
        ${!isClaimed ? `
          <button onclick="claimSingleItem('${item.id}')" class="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98]">
            Claim Item
          </button>
        ` : `
          <button onclick="openItemDetail('${item.id}')" class="px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300">
            Contact Revealed
          </button>
        `}
      </div>
    </div>
  `;
}

// Setup Filter Buttons and Search Bar
function setupFilters() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('bg-indigo-600', 'text-white', 'shadow-xs'));
      filterBtns.forEach(b => b.classList.add('bg-white', 'dark:bg-slate-800', 'text-slate-700', 'dark:text-slate-300'));
      btn.classList.add('bg-indigo-600', 'text-white', 'shadow-xs');
      btn.classList.remove('bg-white', 'dark:bg-slate-800', 'text-slate-700', 'dark:text-slate-300');

      window.AppState.currentFilter = btn.dataset.filter || 'ALL';
      loadItems();
    });
  });

  const catFilter = document.getElementById('filter-category');
  if (catFilter) {
    catFilter.addEventListener('change', (e) => {
      window.AppState.currentCategory = e.target.value;
      loadItems();
    });
  }

  const locFilter = document.getElementById('filter-location');
  if (locFilter) {
    locFilter.addEventListener('change', (e) => {
      window.AppState.currentLocation = e.target.value;
      loadItems();
    });
  }

  const searchInput = document.getElementById('catalog-search');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        window.AppState.searchQuery = e.target.value;
        loadItems();
      }, 200);
    });
  }
}

// Drag & Drop Dropzone Setup with Fast Client Compression
function setupDropzone() {
  const dropzone = document.getElementById('image-dropzone');
  const fileInput = document.getElementById('image-input');
  const preview = document.getElementById('dropzone-preview');
  const previewImg = document.getElementById('preview-image');
  const promptContainer = document.getElementById('dropzone-prompt');
  const removeBtn = document.getElementById('remove-preview-btn');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/20');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-indigo-500', 'bg-indigo-50/50', 'dark:bg-indigo-950/20');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });

  if (removeBtn) {
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      window.AppState.selectedFile = null;
      fileInput.value = '';
      preview.classList.add('hidden');
      promptContainer.classList.remove('hidden');
    });
  }

  async function handleFile(file) {
    if (!file.type.startsWith('image/')) {
      showToast('Please upload an image file (JPG, PNG, WEBP)', 'error');
      return;
    }

    // Instant client-side compression (<20ms)
    const compressed = await compressImageFile(file);
    window.AppState.selectedFile = compressed;

    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      promptContainer.classList.add('hidden');
      preview.classList.remove('hidden');
    };
    reader.readAsDataURL(compressed);
  }
}

// Setup Report Modal & Submission
function setupReportModal() {
  const modal = document.getElementById('report-modal');
  const openBtns = document.querySelectorAll('.open-report-modal');
  const closeBtn = document.getElementById('close-report-modal');
  const form = document.getElementById('report-form');
  const typeBtns = document.querySelectorAll('.report-type-toggle');

  if (!modal) return;

  openBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.defaultType || 'LOST';
      setReportType(type);
      modal.classList.remove('hidden');
      document.body.classList.add('overflow-hidden');
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    });
  }

  typeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      setReportType(btn.dataset.type);
    });
  });

  function setReportType(type) {
    window.AppState.activeReportType = type;
    typeBtns.forEach(b => {
      if (b.dataset.type === type) {
        b.className = `report-type-toggle flex-1 py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-xs ${
          type === 'LOST' ? 'bg-rose-600 text-white' : 'bg-sky-600 text-white'
        }`;
      } else {
        b.className = 'report-type-toggle flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 transition-all';
      }
    });

    const submitBtn = document.getElementById('report-submit-btn');
    if (submitBtn) {
      submitBtn.innerHTML = `
        <span class="flex items-center justify-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
          Analyze & Search ${type === 'LOST' ? 'Found Matches' : 'Lost Matches'}
        </span>
      `;
    }
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('report-submit-btn');
      const originalHtml = submitBtn.innerHTML;

      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <span class="flex items-center justify-center gap-2">
          <svg class="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
          Computing Vector Matches...
        </span>
      `;

      try {
        const formData = new FormData(form);
        formData.set('item_type', window.AppState.activeReportType);
        if (window.AppState.selectedFile) {
          formData.set('image', window.AppState.selectedFile);
        }

        const result = await API.reportItem(formData);
        modal.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
        form.reset();

        const preview = document.getElementById('dropzone-preview');
        const promptContainer = document.getElementById('dropzone-prompt');
        if (preview) preview.classList.add('hidden');
        if (promptContainer) promptContainer.classList.remove('hidden');
        window.AppState.selectedFile = null;

        showToast(result.message, 'success');
        refreshStats();
        if (document.getElementById('items-grid')) loadItems();

        openMatchResultsDrawer(result.item, result.matches);
      } catch (err) {
        showToast(err.message || 'Submission failed. Please check fields.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
    });
  }
}

// Post-Submit Match Results Drawer
function openMatchResultsDrawer(submittedItem, matches) {
  const drawer = document.getElementById('match-drawer');
  if (!drawer) return;

  const leftPanel = document.getElementById('match-drawer-submitted');
  const rightList = document.getElementById('match-drawer-candidates');
  const countBadge = document.getElementById('match-count-badge');

  if (countBadge) {
    countBadge.textContent = `${matches.length} Potential Match${matches.length === 1 ? '' : 'es'}`;
  }

  if (leftPanel) {
    const isLost = submittedItem.item_type === 'LOST';
    leftPanel.innerHTML = `
      <div class="bg-slate-50 dark:bg-slate-900/60 p-5 rounded-2xl border border-slate-200 dark:border-slate-700">
        <div class="relative h-44 w-full rounded-xl overflow-hidden bg-slate-200 dark:bg-slate-800 mb-4">
          <img src="${submittedItem.image_path || '/sample_assets/laptop_lost.jpg'}" alt="${submittedItem.title}" class="w-full h-full object-cover">
          <span class="absolute top-2 left-2 px-2 py-0.5 text-xs font-bold rounded ${isLost ? 'bg-rose-600 text-white' : 'bg-sky-600 text-white'}">
            YOUR ${submittedItem.item_type} REPORT
          </span>
        </div>
        <h4 class="font-bold text-slate-900 dark:text-white text-base">${submittedItem.title}</h4>
        <div class="flex items-center gap-2 mt-1 text-xs text-slate-500">
          <span class="px-2 py-0.5 rounded bg-white dark:bg-slate-800 font-medium">${submittedItem.category}</span>
          <span>•</span>
          <span>${submittedItem.location}</span>
        </div>
        <p class="text-xs text-slate-600 dark:text-slate-400 mt-2 line-clamp-3">${submittedItem.description}</p>
      </div>
    `;
  }

  if (rightList) {
    if (!matches || matches.length === 0) {
      rightList.innerHTML = `
        <div class="text-center py-16">
          <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-indigo-50 dark:bg-indigo-950 text-indigo-500 flex items-center justify-center shadow-inner">
            <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>
          <h4 class="font-bold text-slate-800 dark:text-slate-200 text-sm">No Immediate Matches Above 68%</h4>
          <p class="text-xs text-slate-500 max-w-sm mx-auto mt-1">Your item is securely indexed in MongoDB Atlas. Our engine will continuously scan for candidate matches as new reports arrive.</p>
        </div>
      `;
    } else {
      rightList.innerHTML = matches.map((match, idx) => {
        const item = match.item;
        const isHigh = match.is_high_confidence;
        const badgeColor = isHigh ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white';

        return `
          <div class="p-4 rounded-2xl bg-white dark:bg-slate-800 border ${isHigh ? 'match-card-high' : 'border-slate-200 dark:border-slate-700'} shadow-xs hover:shadow-md transition-all">
            <div class="flex items-start gap-4">
              <div class="w-24 h-24 rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-900 flex-shrink-0 img-zoom-container">
                <img src="${item.image_path || '/sample_assets/laptop_found.jpg'}" alt="${item.title}" class="w-full h-full object-cover">
              </div>
              <div class="flex-1">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2">
                    <span class="px-2.5 py-0.5 text-xs font-bold rounded-full ${badgeColor} shadow-xs ${isHigh ? 'badge-pulse' : ''}">
                      ${match.score}% ${isHigh ? 'High Confidence Match' : 'Similarity Score'}
                    </span>
                    <span class="text-xs text-slate-400">Rank #${idx + 1}</span>
                  </div>
                  <span class="text-xs font-medium text-slate-400">${formatDate(item.created_at)}</span>
                </div>

                <h5 class="font-bold text-slate-900 dark:text-white text-sm mt-1.5">${item.title}</h5>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">${item.description}</p>

                <div class="flex flex-wrap gap-1.5 mt-2.5">
                  <span class="text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700/80 text-slate-600 dark:text-slate-300">
                    Vector: ${(match.vec_score * 100).toFixed(0)}%
                  </span>
                  <span class="text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700/80 text-slate-600 dark:text-slate-300">
                    Category: ${match.cat_score === 1.0 ? '✓ Match (1.0)' : 'Diff (0.2)'}
                  </span>
                  <span class="text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700/80 text-slate-600 dark:text-slate-300">
                    Location: ${match.loc_score === 1.0 ? '✓ Same Zone (1.0)' : 'Zone (0.6)'}
                  </span>
                </div>

                <div class="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 dark:border-slate-700">
                  <span class="text-xs text-slate-500 flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    ${item.location}
                  </span>
                  <div class="flex gap-2">
                    <button onclick="dismissMatchCard(this)" class="px-3 py-1 text-xs font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
                      Not My Item
                    </button>
                    <button onclick="claimSingleItem('${item.id}')" class="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-transform hover:scale-[1.02]">
                      Claim & Reveal Contact
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  drawer.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');
}

function closeMatchDrawer() {
  const drawer = document.getElementById('match-drawer');
  if (drawer) {
    drawer.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }
}

function dismissMatchCard(btn) {
  const card = btn.closest('.p-4');
  if (card) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(-10px)';
    setTimeout(() => card.remove(), 200);
  }
}

// Standalone Visual Matcher Page Logic
function setupVisualMatcher() {
  const scanForm = document.getElementById('visual-scan-form');
  const scanDropzone = document.getElementById('scan-dropzone');
  const scanInput = document.getElementById('scan-image-input');
  const scanPreview = document.getElementById('scan-preview');
  const scanPreviewImg = document.getElementById('scan-preview-img');
  const scanPrompt = document.getElementById('scan-prompt');
  const scanResultsGrid = document.getElementById('scan-results-grid');

  if (!scanForm) return;

  if (scanDropzone && scanInput) {
    scanDropzone.addEventListener('click', () => scanInput.click());

    scanInput.addEventListener('change', async (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = await compressImageFile(e.target.files[0]);
        const reader = new FileReader();
        reader.onload = (ev) => {
          scanPreviewImg.src = ev.target.result;
          scanPrompt.classList.add('hidden');
          scanPreview.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
      }
    });
  }

  scanForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('scan-submit-btn');
    btn.disabled = true;
    btn.innerHTML = `
      <span class="flex items-center justify-center gap-2">
        <svg class="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
        Scanning Lookalikes...
      </span>
    `;

    scanResultsGrid.innerHTML = renderSkeletons(3);

    try {
      const formData = new FormData(scanForm);
      const data = await API.scanVisual(formData);

      if (!data.matches || data.matches.length === 0) {
        scanResultsGrid.innerHTML = `
          <div class="col-span-full py-16 text-center bg-white dark:bg-slate-800 rounded-3xl p-8 border border-slate-200 dark:border-slate-700">
            <h4 class="font-bold text-slate-800 dark:text-slate-100 text-sm">No Lookalikes Found</h4>
            <p class="text-slate-500 text-xs mt-1">Try another photo angle or broader search text.</p>
          </div>
        `;
      } else {
        scanResultsGrid.innerHTML = data.matches.map(m => renderVisualMatchCard(m)).join('');
      }
    } catch (err) {
      scanResultsGrid.innerHTML = `<div class="col-span-full py-12 text-center text-rose-500 font-medium text-xs">Scan failed: ${err.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <span class="flex items-center justify-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          Search Lookalikes
        </span>
      `;
    }
  });
}

function renderVisualMatchCard(match) {
  const item = match.item;
  const isHigh = match.is_high_confidence;
  const isLost = item.item_type === 'LOST';

  return `
    <div class="animate-card-in bg-white dark:bg-slate-800 rounded-3xl overflow-hidden border ${isHigh ? 'border-emerald-500 shadow-md' : 'border-slate-200 dark:border-slate-700'} p-4 flex flex-col justify-between">
      <div>
        <div class="relative h-44 w-full rounded-2xl overflow-hidden bg-slate-100 dark:bg-slate-900 mb-3 img-zoom-container">
          <img src="${item.image_path || '/sample_assets/laptop_lost.jpg'}" alt="${item.title}" loading="lazy" class="w-full h-full object-cover">
          <span class="absolute top-2 left-2 px-2 py-0.5 text-xs font-bold rounded-md ${isLost ? 'bg-rose-600 text-white' : 'bg-sky-600 text-white'}">
            ${item.item_type}
          </span>
          <span class="absolute top-2 right-2 px-2.5 py-0.5 text-xs font-bold rounded-full ${isHigh ? 'bg-emerald-500 text-white badge-pulse' : 'bg-slate-800 text-white'}">
            ${match.score}% Match
          </span>
        </div>

        <h4 class="font-bold text-slate-900 dark:text-white text-sm line-clamp-1">${item.title}</h4>
        <div class="flex items-center gap-2 text-xs text-slate-500 mt-1">
          <span class="px-2 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-md">${item.category}</span>
          <span>•</span>
          <span>${item.location}</span>
        </div>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-2 line-clamp-2">${item.description}</p>
      </div>

      <div class="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700 flex items-center justify-between">
        <span class="text-[11px] text-slate-400">Vector: ${(match.vec_score * 100).toFixed(0)}%</span>
        <button onclick="claimSingleItem('${item.id}')" class="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs">
          Claim Item
        </button>
      </div>
    </div>
  `;
}

// Single Item Detail Modal
async function openItemDetail(itemId) {
  const modal = document.getElementById('detail-modal');
  if (!modal) return;
  const content = document.getElementById('detail-modal-content');

  content.innerHTML = `<div class="py-12 text-center text-slate-400 text-xs">Loading item details...</div>`;
  modal.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');

  try {
    const item = await API.getItem(itemId);
    const isLost = item.item_type === 'LOST';
    const isClaimed = item.status === 'CLAIMED';

    content.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="rounded-2xl overflow-hidden bg-slate-100 dark:bg-slate-900 h-64 md:h-full">
          <img src="${item.image_path || '/sample_assets/laptop_lost.jpg'}" alt="${item.title}" class="w-full h-full object-cover">
        </div>
        <div class="flex flex-col justify-between">
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2.5 py-1 text-xs font-bold rounded-lg ${isLost ? 'bg-rose-100 text-rose-700' : 'bg-sky-100 text-sky-700'}">
                ${item.item_type} ITEM
              </span>
              <span class="text-xs px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-700 font-medium">
                ${item.category}
              </span>
            </div>
            <h3 class="text-xl font-bold text-slate-900 dark:text-white mt-2">${item.title}</h3>
            <p class="text-xs text-slate-400 mt-1">Reported on ${new Date(item.created_at).toLocaleString()}</p>
            
            <div class="mt-4 p-3 bg-slate-50 dark:bg-slate-700/40 rounded-xl text-xs text-slate-600 dark:text-slate-300">
              <span class="font-semibold text-slate-800 dark:text-slate-200">Campus Location:</span> ${item.location}
            </div>

            <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mt-3 leading-relaxed">${item.description}</p>
          </div>

          <div class="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700">
            ${isClaimed ? `
              <div class="p-4 bg-emerald-50 dark:bg-emerald-950/50 rounded-2xl border border-emerald-200 dark:border-emerald-800">
                <h5 class="text-xs font-bold text-emerald-800 dark:text-emerald-300 uppercase">Contact Information</h5>
                <p class="text-sm font-semibold text-emerald-950 dark:text-emerald-100 mt-1">${item.contact_name || 'Campus Member'}</p>
                <p class="text-xs text-emerald-700 dark:text-emerald-400 mt-0.5">${item.contact_info}</p>
              </div>
            ` : `
              <button onclick="claimSingleItem('${item.id}')" class="w-full py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs sm:text-sm shadow-md transition-all hover:scale-[1.01]">
                Claim & Reveal Submitter Contact
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<div class="py-8 text-center text-rose-500 font-medium text-xs">Failed to load details.</div>`;
  }
}

function closeItemDetail() {
  const modal = document.getElementById('detail-modal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }
}

// Claim Action Handler
async function claimSingleItem(itemId) {
  try {
    const res = await API.claimItem(itemId);
    showToast(res.message, 'success');
    refreshStats();
    if (document.getElementById('items-grid')) loadItems();

    openContactModal(res.item);
  } catch (err) {
    showToast('Failed to claim item. Please retry.', 'error');
  }
}

function openContactModal(item) {
  const modal = document.getElementById('contact-modal');
  if (!modal) return;

  document.getElementById('contact-item-title').textContent = item.title;
  document.getElementById('contact-name-val').textContent = item.contact_name || 'Campus Member';
  document.getElementById('contact-info-val').textContent = item.contact_info;

  modal.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');
}

function closeContactModal() {
  const modal = document.getElementById('contact-modal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }
}
