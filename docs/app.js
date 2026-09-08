(function () {
  "use strict";

  const PAGE_SIZE = 30;

  const state = {
    query: "",
    category: "all",
    tag: null,
    sort: "relevance",
    page: 1,
  };

  let items = [];
  let shuffledItems = [];
  let fuse = null;

  const el = {
    search: document.getElementById("search-box"),
    status: document.getElementById("status-line"),
    results: document.getElementById("results"),
    loadMoreWrap: document.getElementById("load-more-wrap"),
    loadMore: document.getElementById("load-more"),
    categoryFilters: document.getElementById("category-filters"),
    sortSelect: document.getElementById("sort-select"),
    resetButton: document.getElementById("reset-button"),
    titleReset: document.getElementById("title-reset"),
    activeTagFilter: document.getElementById("active-tag-filter"),
    activeTagName: document.getElementById("active-tag-name"),
    clearTagFilter: document.getElementById("clear-tag-filter"),
    dataUpdated: document.getElementById("data-updated"),
  };

  function shuffleArray(arr) {
    // Fisher-Yates
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return iso;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function itemLink(item) {
    return item.source_url || item.episode_video_url || item.episode_blog_url || null;
  }

  function matchesFilters(item) {
    if (state.category !== "all" && item.category !== state.category) return false;
    if (state.tag && !(item.tags || []).includes(state.tag)) return false;
    return true;
  }

  function currentResultSet() {
    let base;
    if (state.query.trim() && fuse) {
      base = fuse.search(state.query.trim(), { limit: 2000 }).map((r) => r.item);
    } else {
      // No active search: browse in shuffled order so every visit/reset
      // surfaces something new, rather than always the same file order.
      base = shuffledItems;
    }
    let filtered = base.filter(matchesFilters);

    if (state.sort === "date-desc") {
      filtered = filtered.slice().sort((a, b) => (b.episode_date || "").localeCompare(a.episode_date || ""));
    } else if (state.sort === "date-asc") {
      filtered = filtered.slice().sort((a, b) => (a.episode_date || "").localeCompare(b.episode_date || ""));
    }
    return filtered;
  }

  function renderCard(item) {
    const link = itemLink(item);
    const titleHtml = link
      ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>`
      : escapeHtml(item.title);

    const metaParts = [];
    if (item.creator) metaParts.push(escapeHtml(item.creator));
    if (item.episode_number != null) metaParts.push(`Episode ${item.episode_number}`);
    if (item.episode_date) metaParts.push(formatDate(item.episode_date));
    if (item.edition === "adafruit") metaParts.push("Adafruit Edition");

    const tagsHtml = (item.tags || [])
      .slice(0, 8)
      .map((t) => `<button class="tag-chip" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</button>`)
      .join("");

    const links = [];
    if (item.source_url) links.push(`<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Source</a>`);
    if (item.episode_video_url) links.push(`<a href="${escapeHtml(item.episode_video_url)}" target="_blank" rel="noopener">Watch episode</a>`);
    if (item.episode_blog_url) links.push(`<a href="${escapeHtml(item.episode_blog_url)}" target="_blank" rel="noopener">Episode notes</a>`);

    return `
      <article class="card">
        <div class="card-top">
          <h2 class="card-title">${titleHtml}</h2>
          <span class="badge ${escapeHtml(item.category || "")}">${escapeHtml(item.category || "")}</span>
        </div>
        <p class="card-meta">${metaParts.join(" &middot; ")}</p>
        ${item.synopsis ? `<p class="card-synopsis">${escapeHtml(item.synopsis)}</p>` : ""}
        ${tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : ""}
        ${links.length ? `<div class="card-links">${links.join("")}</div>` : ""}
      </article>
    `;
  }

  function render() {
    const results = currentResultSet();
    const visible = results.slice(0, state.page * PAGE_SIZE);

    el.status.textContent = state.query.trim() || state.tag || state.category !== "all"
      ? `${results.length.toLocaleString()} result${results.length === 1 ? "" : "s"}`
      : `${items.length.toLocaleString()} items in the archive`;

    if (visible.length === 0) {
      el.results.innerHTML = `<div class="no-results">No matches. Try a different search term or clear filters.</div>`;
    } else {
      el.results.innerHTML = visible.map(renderCard).join("");
    }

    el.loadMoreWrap.hidden = visible.length >= results.length;

    if (state.tag) {
      el.activeTagFilter.hidden = false;
      el.activeTagName.textContent = state.tag;
    } else {
      el.activeTagFilter.hidden = true;
    }
  }

  function resetPageAndRender() {
    state.page = 1;
    render();
  }

  function resetAll() {
    state.query = "";
    state.category = "all";
    state.tag = null;
    state.sort = "relevance";
    state.page = 1;

    el.search.value = "";
    el.categoryFilters.querySelectorAll(".filter-chip").forEach((b) => {
      b.classList.toggle("active", b.dataset.category === "all");
    });
    el.sortSelect.value = "relevance";

    shuffledItems = shuffleArray(items.slice());
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // --- events ---
  let searchDebounce = null;
  el.search.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    const wasEmpty = state.query === "";
    const value = el.search.value;
    searchDebounce = setTimeout(() => {
      // Clearing the box (via the native "x" or backspacing to empty) is
      // one of the three reset gestures -- also drop category/tag/sort
      // back to defaults and reshuffle, not just the search text.
      if (value === "" && !wasEmpty) {
        resetAll();
        return;
      }
      state.query = value;
      resetPageAndRender();
    }, 120);
  });

  el.resetButton.addEventListener("click", resetAll);
  el.titleReset.addEventListener("click", resetAll);

  el.categoryFilters.addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-chip");
    if (!btn) return;
    el.categoryFilters.querySelectorAll(".filter-chip").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.category = btn.dataset.category;
    resetPageAndRender();
  });

  el.sortSelect.addEventListener("change", () => {
    state.sort = el.sortSelect.value;
    resetPageAndRender();
  });

  el.results.addEventListener("click", (e) => {
    const chip = e.target.closest(".tag-chip");
    if (!chip) return;
    state.tag = chip.dataset.tag;
    resetPageAndRender();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  el.clearTagFilter.addEventListener("click", () => {
    state.tag = null;
    resetPageAndRender();
  });

  el.loadMore.addEventListener("click", () => {
    state.page += 1;
    render();
  });

  // --- init ---
  fetch("data.json")
    .then((r) => r.json())
    .then((payload) => {
      items = payload.items || payload;
      shuffledItems = shuffleArray(items.slice());
      el.dataUpdated.textContent = payload.generated_at ? formatDate(payload.generated_at.slice(0, 10)) : "recently";

      fuse = new Fuse(items, {
        keys: [
          { name: "title", weight: 0.4 },
          { name: "creator", weight: 0.2 },
          { name: "synopsis", weight: 0.2 },
          { name: "tags", weight: 0.2 },
        ],
        threshold: 0.32,
        ignoreLocation: true,
        minMatchCharLength: 2,
      });

      render();
    })
    .catch((err) => {
      el.status.textContent = "Couldn't load the archive data. Please try refreshing.";
      console.error(err);
    });
})();
