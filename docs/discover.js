(function () {
  "use strict";

  const el = {
    slot: document.getElementById("discover-card-slot"),
    kicker: document.getElementById("pick-kicker"),
    shuffle: document.getElementById("shuffle-button"),
  };

  let items = [];

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

  // Simple deterministic string hash (djb2) so the same date always maps
  // to the same index -- today's pick stays stable across opens/reloads
  // on the same day, and (very likely) changes the next day.
  function hashString(s) {
    let h = 5381;
    for (let i = 0; i < s.length; i++) {
      h = (h * 33) ^ s.charCodeAt(i);
    }
    return h >>> 0;
  }

  function todayKey() {
    return new Date().toISOString().slice(0, 10); // YYYY-MM-DD, UTC-based but stable enough for "changes daily"
  }

  function todaysIndex() {
    return hashString(todayKey()) % items.length;
  }

  const THEME_COUNT = 6;
  function applyDailyTheme() {
    const n = hashString(todayKey() + ":theme") % THEME_COUNT;
    document.body.classList.add(`theme-${n}`);
  }

  function randomIndex() {
    return Math.floor(Math.random() * items.length);
  }

  function renderItem(item, kickerLabel) {
    el.kicker.textContent = kickerLabel;

    const metaParts = [];
    if (item.creator) metaParts.push(escapeHtml(item.creator));
    if (item.episode_number != null) metaParts.push(`Episode ${item.episode_number}`);
    if (item.episode_date) metaParts.push(formatDate(item.episode_date));

    const tagsHtml = (item.tags || [])
      .slice(0, 6)
      .map((t) => `<a class="tag-chip" href="index.html?tag=${encodeURIComponent(t)}">${escapeHtml(t)}</a>`)
      .join("");

    const links = [];
    if (item.source_url) links.push(`<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">See the source</a>`);
    if (item.episode_video_url) links.push(`<a class="secondary" href="${escapeHtml(item.episode_video_url)}" target="_blank" rel="noopener">Watch the episode</a>`);
    if (item.episode_blog_url && !item.source_url) links.push(`<a class="secondary" href="${escapeHtml(item.episode_blog_url)}" target="_blank" rel="noopener">Episode notes</a>`);

    const titleHtml = item.source_url
      ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>`
      : escapeHtml(item.title);

    el.slot.innerHTML = `
      <article class="discover-card">
        <span class="badge ${escapeHtml(item.category || "")}">${escapeHtml(item.category || "")}</span>
        <h1>${titleHtml}</h1>
        <p class="card-meta">${metaParts.join(" &middot; ")}</p>
        ${item.synopsis ? `<p class="card-synopsis">${escapeHtml(item.synopsis)}</p>` : ""}
        ${tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : ""}
        ${links.length ? `<div class="card-links">${links.join("")}</div>` : ""}
      </article>
    `;
  }

  function showToday() {
    renderItem(items[todaysIndex()], "Today's pick");
  }

  function showRandom() {
    renderItem(items[randomIndex()], "Random pick");
  }

  el.shuffle.addEventListener("click", showRandom);

  applyDailyTheme();

  fetch("data.json")
    .then((r) => r.json())
    .then((payload) => {
      items = payload.items || payload;
      if (!items.length) throw new Error("empty dataset");
      showToday();
    })
    .catch((err) => {
      el.slot.innerHTML = `<div class="discover-error">Couldn't load the archive. Please try again.</div>`;
      console.error(err);
    });
})();
