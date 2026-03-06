/**
 * Queue – real-time monitoring dashboard
 * Polls the queue_data endpoint every few seconds and re-renders the UI.
 * For non-today dates, displays a static schedule view (no polling, no actions).
 */
(function () {
  "use strict";

  const POLL_INTERVAL = 5000; // 5 seconds
  let pollTimer = null;
  let lastJson = null;

  // ─── DOM refs ───────────────────────────────────────────────────────
  const $staffView     = document.getElementById("staff-queue-view");
  const $ownerView     = document.getElementById("owner-queue-view");
  const $scheduleView  = document.getElementById("schedule-view");
  const $scheduleList  = document.getElementById("schedule-list");
  const $schedTotal    = document.getElementById("sched-total");
  const $statTotal     = document.getElementById("stat-total");
  const $statServing   = document.getElementById("stat-serving");
  const $statWaiting   = document.getElementById("stat-waiting");
  const $nowSection    = document.getElementById("now-serving-section");
  const $nowContent    = document.getElementById("now-serving-content");
  const $waitSection   = document.getElementById("waiting-section");
  const $waitBadge     = document.getElementById("waiting-badge");
  const $waitList      = document.getElementById("waiting-list");
  const $empty         = document.getElementById("queue-empty");
  const $emptyTitle    = document.getElementById("empty-title");
  const $emptySubtitle = document.getElementById("empty-subtitle");
  const $liveIndicator = document.getElementById("live-indicator");

  // ─── Helpers ────────────────────────────────────────────────────────
  function speciesEmoji(s) {
    const map = { dog: "🐶", cat: "🐱", bird: "🐦" };
    return map[s] || "🐾";
  }

  function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // ─── Render a queue card (live queue) ───────────────────────────────
  function cardHtml(item, isServing) {
    const ownerLine = IS_STAFF ? `${escHtml(item.owner_name)} · ` : "";
    const reasonLine = item.reason
      ? `<div class="apt-card__reason">"${escHtml(item.reason)}"</div>`
      : "";

    const statusPill = `
      <span class="apt-pill ${item.status}">
        <span class="apt-pill__dot"></span>
        ${escHtml(item.status_display)}
      </span>`;

    const actions = isServing && IS_STAFF
      ? `<div class="queue-actions">
           <button class="queue-action-btn queue-action-btn--complete"
                   onclick="queueAction(${item.id}, 'completed')"
                   title="Mark as completed">
             <i class="fa-solid fa-check"></i> Completed
           </button>
           <button class="queue-action-btn queue-action-btn--noshow"
                   onclick="queueAction(${item.id}, 'no_show')"
                   title="Mark as no show">
             <i class="fa-solid fa-user-xmark"></i> No Show
           </button>
         </div>`
      : "";

    const servingClass = isServing ? "apt-card--serving" : "";
    const isOwn = item.owner_id === USER_ID;
    const ownClass = isOwn ? "apt-card--mine" : "";
    const queueNumHtml = isServing && IS_STAFF && item.queue_number
      ? `<span class="queue-number-badge">#${item.queue_number}</span>`
      : "";

    return `
      <div class="apt-card ${item.status} ${servingClass} ${ownClass}">
        ${queueNumHtml}
        <div class="apt-card__time">
          <div class="apt-card__time-val">${escHtml(item.start_time)}</div>
          <div class="apt-card__time-ampm">${escHtml(item.start_time_ampm)}</div>
        </div>
        <div class="apt-card__pet-icon">${speciesEmoji(item.species)}</div>
        <div class="apt-card__info">
          <div class="apt-card__pet-name">${escHtml(item.pet_name)}${isOwn && !IS_STAFF ? ' <span class="apt-card__you-tag">You</span>' : ""}</div>
          <div class="apt-card__meta">${ownerLine}${escHtml(item.appointment_type)}</div>
          ${reasonLine}
        </div>
        ${statusPill}
        ${actions}
      </div>`;
  }

  // ─── Build schedule card (non-today, read-only) ─────────────────────
  function scheduleCardHtml(item) {
    const ownerLine = IS_STAFF ? `${escHtml(item.owner_name)} · ` : "";
    const reasonLine = item.reason
      ? `<div class="apt-card__reason">"${escHtml(item.reason)}"</div>`
      : "";

    const statusPill = `
      <span class="apt-pill ${item.status}">
        <span class="apt-pill__dot"></span>
        ${escHtml(item.status_display)}
      </span>`;

    return `
      <div class="apt-card ${item.status}">
        <div class="apt-card__time">
          <div class="apt-card__time-val">${escHtml(item.start_time)}</div>
          <div class="apt-card__time-ampm">${escHtml(item.start_time_ampm)}</div>
        </div>
        <div class="apt-card__pet-icon">${speciesEmoji(item.species)}</div>
        <div class="apt-card__info">
          <div class="apt-card__pet-name">${escHtml(item.pet_name)}</div>
          <div class="apt-card__meta">${ownerLine}${escHtml(item.appointment_type)}</div>
          ${reasonLine}
        </div>
        ${statusPill}
      </div>`;
  }

  // ─── Build owner card (for owner-only live view) ────────────────────
  function ownerCardHtml(info) {
    const reasonLine = info.reason
      ? `<div class="apt-card__reason">"${escHtml(info.reason)}"</div>`
      : "";

    return `
      <div class="apt-card ${info.status} apt-card--mine ${info.is_now_serving ? 'apt-card--serving' : ''}">
        <div class="apt-card__time">
          <div class="apt-card__time-val">${escHtml(info.start_time)}</div>
          <div class="apt-card__time-ampm">${escHtml(info.start_time_ampm)}</div>
        </div>
        <div class="apt-card__pet-icon">${speciesEmoji(info.species)}</div>
        <div class="apt-card__info">
          <div class="apt-card__pet-name">${escHtml(info.pet_name)}</div>
          <div class="apt-card__meta">${escHtml(info.appointment_type)}</div>
          ${reasonLine}
        </div>
        <span class="apt-pill ${info.status}">
          <span class="apt-pill__dot"></span>
          ${escHtml(info.status_display)}
        </span>
      </div>`;
  }

  // ─── Render schedule view (non-today) ───────────────────────────────
  function renderScheduleView(data) {
    $staffView.style.display  = "none";
    $ownerView.style.display  = "none";
    $liveIndicator.style.display = "none";

    const items = data.scheduled || [];

    if (items.length === 0) {
      $scheduleView.style.display = "none";
      $emptyTitle.textContent = "No appointments";
      $emptySubtitle.textContent = "There are no appointments scheduled for this date.";
      $empty.style.display = "block";
      return;
    }

    $empty.style.display = "none";
    $scheduleView.style.display = "block";
    $schedTotal.textContent = items.length;
    $scheduleList.innerHTML = items.map(function (item) {
      return scheduleCardHtml(item);
    }).join("");
  }

  // ─── Render owner-only view (today) ─────────────────────────────────
  function renderOwnerView(data) {
    $staffView.style.display    = "none";
    $scheduleView.style.display = "none";

    if (!data.my_queue_info || data.my_queue_info.length === 0) {
      $ownerView.style.display = "none";
      $emptyTitle.textContent = "No patients in queue";
      $emptySubtitle.textContent = "No pending or confirmed appointments for this day.";
      $empty.style.display = "block";
      return;
    }

    $empty.style.display = "none";
    $ownerView.style.display = "block";

    let html = "";
    data.my_queue_info.forEach(function (info) {
      // Status message
      let statusIcon, statusMsg, statusClass;
      if (info.is_now_serving) {
        statusIcon = '<i class="fa-solid fa-bell-concierge"></i>';
        statusMsg = "It's your turn! Your pet is now being served.";
        statusClass = "owner-status--serving";
      } else if (info.ahead === 0) {
        statusIcon = '<i class="fa-solid fa-bell-concierge"></i>';
        statusMsg = "You're next! Please be ready.";
        statusClass = "owner-status--next";
      } else if (info.ahead === 1) {
        statusIcon = '<i class="fa-solid fa-hourglass-half"></i>';
        statusMsg = "There is <strong>1</strong> client before you. You're almost up!";
        statusClass = "owner-status--waiting";
      } else {
        statusIcon = '<i class="fa-solid fa-hourglass-half"></i>';
        statusMsg = `There are <strong>${info.ahead}</strong> clients before you. Please wait for a while.`;
        statusClass = "owner-status--waiting";
      }

      html += `
        <div class="owner-queue-entry">
          <div class="owner-status ${statusClass}">
            <span class="owner-status__icon">${statusIcon}</span>
            <div class="owner-status__body">
              <div class="owner-status__position">Queue Position: <strong>#${info.position}</strong></div>
              <div class="owner-status__message">${statusMsg}</div>
            </div>
          </div>
          ${ownerCardHtml(info)}
        </div>`;
    });

    $ownerView.innerHTML = html;
  }

  // ─── Render staff view (today) ──────────────────────────────────────
  function renderStaffView(data) {
    $ownerView.style.display    = "none";
    $scheduleView.style.display = "none";
    $staffView.style.display    = "block";

    // Stats
    $statTotal.textContent   = data.total_count;
    $statServing.textContent = data.now_serving ? "#" + data.now_serving.queue_number : "—";
    $statWaiting.textContent = data.waiting_count;

    if (data.total_count === 0) {
      $nowSection.style.display  = "none";
      $waitSection.style.display = "none";
      $staffView.style.display   = "none";
      $emptyTitle.textContent = "No patients in queue";
      $emptySubtitle.textContent = "No pending or confirmed appointments for this day.";
      $empty.style.display       = "block";
      return;
    }

    $empty.style.display = "none";

    // Now Serving
    if (data.now_serving) {
      $nowSection.style.display = "block";
      $nowContent.innerHTML = cardHtml(data.now_serving, true);
    } else {
      $nowSection.style.display = "none";
    }

    // Waiting
    if (data.waiting.length > 0) {
      $waitSection.style.display = "block";
      $waitBadge.textContent = data.waiting_count;
      $waitList.innerHTML = data.waiting
        .map(function (item) {
          return `<div class="queue-position">
                    <span class="queue-position__number">#${item.queue_number}</span>
                    ${cardHtml(item, false)}
                  </div>`;
        })
        .join("");
    } else {
      $waitSection.style.display = "none";
    }
  }

  // ─── Render (dispatch to correct view) ──────────────────────────────
  function render(data) {
    // Non-today → schedule view (no live queue)
    if (!data.is_today) {
      renderScheduleView(data);
      return;
    }

    // Today → live queue
    if (IS_STAFF) {
      renderStaffView(data);
    } else {
      renderOwnerView(data);
    }
  }

  // ─── Fetch data ─────────────────────────────────────────────────────
  function fetchQueue() {
    const url = QUEUE_DATA_URL + "?date=" + VIEW_DATE;
    fetch(url, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        // Only re-render if data changed
        const json = JSON.stringify(data);
        if (json !== lastJson) {
          lastJson = json;
          render(data);
        }
        $liveIndicator.classList.remove("live--error");
      })
      .catch(function () {
        $liveIndicator.classList.add("live--error");
      });
  }

  // ─── Queue action (Completed / No Show) ─────────────────────────────
  window.queueAction = function (aptId, action) {
    const body = new FormData();
    body.append("appointment_id", aptId);
    body.append("action", action);
    body.append("csrfmiddlewaretoken", CSRF_TOKEN);

    fetch(QUEUE_ACTION_URL, {
      method: "POST",
      credentials: "same-origin",
      body: body,
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        // Redirect to post-completion page if URL provided
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
          return;
        }
        // Otherwise refresh queue
        fetchQueue();
      })
      .catch(function (err) {
        alert("Action failed: " + err.message);
      });
  };

  // ─── Start ──────────────────────────────────────────────────────────
  fetchQueue();

  // Only poll if viewing today's queue
  if (IS_TODAY) {
    pollTimer = setInterval(fetchQueue, POLL_INTERVAL);

    // Pause polling when tab hidden, resume when visible
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        clearInterval(pollTimer);
        pollTimer = null;
      } else {
        fetchQueue();
        pollTimer = setInterval(fetchQueue, POLL_INTERVAL);
      }
    });
  } else {
    // Hide the live indicator for non-today dates
    $liveIndicator.style.display = "none";
  }
})();
