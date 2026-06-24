const studentSelect = document.querySelector('#studentSelect');
const dateInput = document.querySelector('#dateInput');
const loadButton = document.querySelector('#loadButton');
const previousDayButton = document.querySelector('#previousDayButton');
const nextDayButton = document.querySelector('#nextDayButton');
const instructorFilter = document.querySelector('#instructorFilter');
const aircraftFilter = document.querySelector('#aircraftFilter');
const segmentButtons = [...document.querySelectorAll('.segment[data-window]')];
const quickDateButtons = [...document.querySelectorAll('.quick-date[data-date-offset]')];
const clearFiltersButton = document.querySelector('#clearFiltersButton');
const activeFilterChips = document.querySelector('#activeFilterChips');
const availabilityBody = document.querySelector('#availabilityBody');
const availabilityCount = document.querySelector('#availabilityCount');
const availabilityTitle = document.querySelector('#availabilityTitle');
const scheduleTimeline = document.querySelector('#scheduleTimeline');
const bookingsList = document.querySelector('#bookingsList');
const resourceInsights = document.querySelector('#resourceInsights');
const recommendationCard = document.querySelector('#recommendationCard');
const message = document.querySelector('#message');
const selectedStudentLabel = document.querySelector('#selectedStudentLabel');
const nextOpenLabel = document.querySelector('#nextOpenLabel');
const filteredViewLabel = document.querySelector('#filteredViewLabel');
const slotMetric = document.querySelector('#slotMetric');
const bookingMetric = document.querySelector('#bookingMetric');
const instructorMetric = document.querySelector('#instructorMetric');
const aircraftMetric = document.querySelector('#aircraftMetric');
const serviceMetric = document.querySelector('#serviceMetric');
const serviceMetricCard = serviceMetric.closest('.metric');

const state = {
  students: [],
  instructors: [],
  aircraft: [],
  slots: [],
  filteredSlots: [],
  bookings: [],
  filterWindow: 'all',
  loading: false
};

const icons = {
  book: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6h13"></path><path d="M8 12h13"></path><path d="M8 18h13"></path><path d="M3 6h.01"></path><path d="M3 12h.01"></path><path d="M3 18h.01"></path></svg>',
  cancel: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>',
  close: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>'
};

const modal = document.createElement('div');
modal.id = 'modal';
modal.className = 'modal hidden';
modal.innerHTML = `
  <div class="modal-inner" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
    <div class="modal-header">
      <h2 id="modalTitle" class="modal-title">Output</h2>
      <button id="modalClose" class="modal-close" type="button" aria-label="Close dialog" title="Close dialog">
        ${icons.close}
      </button>
    </div>
    <pre id="modalContent" class="modal-content"></pre>
  </div>
`;
document.body.appendChild(modal);

function nextUsefulDate() {
  const now = new Date();
  const result = new Date(now);
  result.setDate(now.getDate() + 7);
  while (result.getDay() === 0) {
    result.setDate(result.getDate() + 1);
  }
  return toDateInputValue(result);
}

function toDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function setMessage(text, kind = '') {
  message.hidden = !text;
  message.textContent = text || '';
  message.className = `message ${kind}`.trim();
}

function setBusy(isBusy) {
  state.loading = isBusy;
  loadButton.disabled = isBusy;
  previousDayButton.disabled = isBusy;
  nextDayButton.disabled = isBusy;
  studentSelect.disabled = isBusy;
  dateInput.disabled = isBusy;
  instructorFilter.disabled = isBusy;
  aircraftFilter.disabled = isBusy;
  segmentButtons.forEach(button => {
    button.disabled = isBusy;
  });
  quickDateButtons.forEach(button => {
    button.disabled = isBusy;
  });
  clearFiltersButton.disabled = isBusy;
}

function showModal(title, text) {
  document.querySelector('#modalTitle').textContent = title;
  document.querySelector('#modalContent').textContent = text || '';
  modal.classList.remove('hidden');
  document.body.classList.add('modal-open');
  document.querySelector('#modalClose').focus();
}

function closeModal() {
  modal.classList.add('hidden');
  document.body.classList.remove('modal-open');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error?.message || `Request failed with ${response.status}`);
  }
  return payload;
}

function selectedStudentId() {
  return Number(studentSelect.value);
}

function selectedStudent() {
  return state.students.find(student => Number(student.id) === selectedStudentId());
}

function studentDisplayName() {
  return selectedStudent()?.name || 'Selected student';
}

function initials(name) {
  return String(name || '')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() || '')
    .join('');
}

function splitLocalDisplay(value) {
  const [date = '', time = '', zone = ''] = String(value || '').split(' ');
  return { date, time, zone };
}

function formatDateLabel(value) {
  if (!value) return '';
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(new Date(year, month - 1, day));
}

function formatTimeRange(startLocal, endLocal) {
  const start = splitLocalDisplay(startLocal);
  const end = splitLocalDisplay(endLocal);
  const endZone = end.zone || start.zone;
  return {
    time: `${start.time} - ${end.time}`,
    date: `${start.date} ${endZone}`.trim()
  };
}

function formatDeadline(utcValue) {
  if (!utcValue) return 'Deadline unavailable';
  const date = new Date(utcValue);
  if (Number.isNaN(date.getTime())) return utcValue;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short'
  }).format(date);
}

function startHour(slot) {
  const { time } = splitLocalDisplay(slot.startLocal);
  return Number(time.split(':')[0]);
}

function formatHourLabel(hour) {
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalized = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalized}:00 ${suffix}`;
}

function slotMatchesWindow(slot) {
  const hour = startHour(slot);
  if (state.filterWindow === 'morning') return hour < 12;
  if (state.filterWindow === 'afternoon') return hour >= 12 && hour < 17;
  if (state.filterWindow === 'evening') return hour >= 17;
  return true;
}

function applySlotFilters() {
  const instructorId = instructorFilter.value;
  const aircraftId = aircraftFilter.value;
  state.filteredSlots = state.slots.filter(slot => {
    const matchesInstructor = instructorId === 'all' || Number(slot.instructorId) === Number(instructorId);
    const matchesAircraft = aircraftId === 'all' || Number(slot.aircraftId) === Number(aircraftId);
    return matchesInstructor && matchesAircraft && slotMatchesWindow(slot);
  });
  return state.filteredSlots;
}

function selectedOptionText(select) {
  return select.options[select.selectedIndex]?.textContent || '';
}

function activeFilterLabels() {
  const labels = [];
  if (instructorFilter.value !== 'all') labels.push(`Instructor: ${selectedOptionText(instructorFilter)}`);
  if (aircraftFilter.value !== 'all') labels.push(`Aircraft: ${selectedOptionText(aircraftFilter)}`);
  if (state.filterWindow !== 'all') {
    const activeSegment = segmentButtons.find(button => button.dataset.window === state.filterWindow);
    labels.push(`Window: ${activeSegment?.textContent || state.filterWindow}`);
  }
  return labels;
}

function renderFilterChips() {
  const labels = activeFilterLabels();
  activeFilterChips.innerHTML = labels.length
    ? labels.map(label => `<span class="filter-chip">${escapeHtml(label)}</span>`).join('')
    : '<span class="filter-chip">All filters clear</span>';
  clearFiltersButton.disabled = state.loading || labels.length === 0;
}

function updateCommandContext() {
  const nextSlot = state.filteredSlots[0];
  if (nextSlot) {
    const range = formatTimeRange(nextSlot.startLocal, nextSlot.endLocal);
    nextOpenLabel.textContent = `${range.time} ${range.date}`;
  } else {
    nextOpenLabel.textContent = 'No open match';
  }
  const labels = activeFilterLabels();
  filteredViewLabel.textContent = labels.length ? `${labels.length} active` : 'All resources';
  renderFilterChips();
}

function countBy(slots, key, labelKey) {
  const counts = new Map();
  slots.forEach(slot => {
    const id = slot[key];
    const existing = counts.get(id) || { name: slot[labelKey], count: 0 };
    existing.count += 1;
    counts.set(id, existing);
  });
  return [...counts.values()].sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
}

function renderResourceInsights() {
  const instructorCounts = countBy(state.filteredSlots, 'instructorId', 'instructorName');
  const aircraftCounts = countBy(state.filteredSlots, 'aircraftId', 'tailNumber');
  const rows = [
    ...instructorCounts.map(item => ({ ...item, type: 'Instructor' })),
    ...aircraftCounts.map(item => ({ ...item, type: 'Aircraft' }))
  ];
  const maxCount = Math.max(1, ...rows.map(row => row.count));

  if (rows.length === 0) {
    resourceInsights.innerHTML = `
      <div class="resource-card">
        <span class="resource-name">No resource activity</span>
        <span class="resource-count">Adjust filters or date</span>
      </div>
    `;
    return;
  }

  resourceInsights.innerHTML = rows.map(row => {
    const fill = Math.round((row.count / maxCount) * 100);
    return `
      <div class="resource-card">
        <div class="resource-card-header">
          <span>
            <span class="resource-name">${escapeHtml(row.name)}</span>
            <span class="person-meta">${escapeHtml(row.type)}</span>
          </span>
          <span class="resource-count">${row.count} slot${row.count === 1 ? '' : 's'}</span>
        </div>
        <span class="resource-bar" aria-hidden="true"><span style="--fill: ${fill}%"></span></span>
      </div>
    `;
  }).join('');
}

function renderRecommendation() {
  const slot = state.filteredSlots[0];
  if (!slot) {
    recommendationCard.classList.add('is-empty');
    recommendationCard.innerHTML = `
      <div class="recommendation-title">
        <strong>No matching lesson</strong>
        <span class="person-meta">Change the date or filters to surface an available option.</span>
      </div>
    `;
    return;
  }

  const range = formatTimeRange(slot.startLocal, slot.endLocal);
  recommendationCard.classList.remove('is-empty');
  recommendationCard.innerHTML = `
    <div class="recommendation-title">
      <strong>${escapeHtml(range.time)}</strong>
      <span class="person-meta">${escapeHtml(range.date)} / ${escapeHtml(studentDisplayName())}</span>
    </div>
    <div class="recommendation-grid">
      <span class="recommendation-stat">
        <span>Instructor</span>
        <strong>${escapeHtml(slot.instructorName)}</strong>
      </span>
      <span class="recommendation-stat">
        <span>Aircraft</span>
        <strong>${escapeHtml(slot.tailNumber)}</strong>
      </span>
    </div>
    <button class="recommendation-action" type="button" data-recommendation-index="0">
      ${icons.book}
      Book recommended lesson
    </button>
  `;
}

function updateSummary() {
  slotMetric.textContent = state.slots.length;
  bookingMetric.textContent = state.bookings.length;
  instructorMetric.textContent = state.instructors.length;
  aircraftMetric.textContent = state.aircraft.filter(plane => Number(plane.active) !== 0).length;

  const student = selectedStudent();
  const dateLabel = formatDateLabel(dateInput.value);
  selectedStudentLabel.textContent = student
    ? `${student.name} / ${dateLabel} / Pacific/Honolulu`
    : `${dateLabel} / Pacific/Honolulu`;
  availabilityTitle.textContent = `Open lesson windows for ${dateLabel || 'selected date'}`;
  updateCommandContext();
}

function renderAvailabilityLoading() {
  availabilityCount.textContent = 'Loading';
  scheduleTimeline.innerHTML = Array.from({ length: 8 }, () => `
    <div class="timeline-slot">
      <span class="skeleton-block short"></span>
      <span class="skeleton-block"></span>
      <span class="skeleton-block short"></span>
    </div>
  `).join('');
  availabilityBody.innerHTML = Array.from({ length: 5 }, () => `
    <tr class="skeleton-row">
      <td><span class="skeleton-block"></span></td>
      <td><span class="skeleton-block short"></span></td>
      <td><span class="skeleton-block"></span></td>
      <td><span class="skeleton-block short"></span></td>
    </tr>
  `).join('');
}

function renderBookingsLoading() {
  bookingsList.innerHTML = Array.from({ length: 3 }, () => `
    <section class="booking-skeleton" aria-hidden="true">
      <span class="skeleton-block"></span>
      <span class="skeleton-block short"></span>
      <span class="skeleton-block"></span>
      <span class="skeleton-block short"></span>
    </section>
  `).join('');
}

function renderTimeline(slots) {
  const hours = Array.from({ length: 12 }, (_, index) => index + 8);
  const counts = new Map();
  slots.forEach(slot => {
    const hour = startHour(slot);
    counts.set(hour, (counts.get(hour) || 0) + 1);
  });
  const maxCount = Math.max(1, ...counts.values());

  scheduleTimeline.innerHTML = hours.map(hour => {
    const count = counts.get(hour) || 0;
    const fill = Math.round((count / maxCount) * 100);
    return `
      <div class="timeline-slot ${count ? 'is-open' : ''}">
        <span class="timeline-hour">${formatHourLabel(hour)}</span>
        <span class="timeline-meter" aria-hidden="true">
          <span class="timeline-fill" style="--fill: ${fill}%"></span>
        </span>
        <span class="timeline-count">${count} slot${count === 1 ? '' : 's'}</span>
      </div>
    `;
  }).join('');
}

function renderFilteredAvailability() {
  const filteredSlots = applySlotFilters();
  renderTimeline(filteredSlots);
  renderAvailability(filteredSlots);
  renderResourceInsights();
  renderRecommendation();
  updateSummary();
}

function renderAvailability(slots) {
  const isFiltered = slots.length !== state.slots.length;
  availabilityCount.textContent = isFiltered
    ? `${slots.length} of ${state.slots.length} slots`
    : `${slots.length} slot${slots.length === 1 ? '' : 's'}`;
  if (slots.length === 0) {
    const emptyText = state.slots.length
      ? 'No slots match the current filters.'
      : 'Try another date or student.';
    availabilityBody.innerHTML = `
      <tr>
        <td colspan="4" class="empty-state">
          <span class="empty-state-content">
            <strong>No matching slots</strong>
            <span>${emptyText}</span>
          </span>
        </td>
      </tr>
    `;
    return;
  }

  let lastHour = null;
  availabilityBody.innerHTML = slots.map((slot, index) => {
    const range = formatTimeRange(slot.startLocal, slot.endLocal);
    const hour = startHour(slot);
    const groupedHeader = hour !== lastHour
      ? `<tr class="group-row"><td colspan="4">${formatHourLabel(hour)}</td></tr>`
      : '';
    lastHour = hour;
    return `
      ${groupedHeader}
      <tr class="slot-row">
        <td data-label="Time">
          <span class="time-stack">
            <span class="time-main">${escapeHtml(range.time)}</span>
            <span class="row-meta-line">
              <span class="time-meta">${escapeHtml(range.date)}</span>
              <span class="row-chip">Open</span>
              <span class="row-chip">60 min</span>
            </span>
          </span>
        </td>
        <td data-label="Instructor">
          <span class="person">
            <span class="avatar" aria-hidden="true">${escapeHtml(initials(slot.instructorName))}</span>
            <span>
              <span class="person-name">${escapeHtml(slot.instructorName)}</span>
              <span class="person-meta">Instructor</span>
            </span>
          </span>
        </td>
        <td data-label="Aircraft">
          <span class="aircraft-stack">
            <span class="aircraft-tail">${escapeHtml(slot.tailNumber)}</span>
            <span class="aircraft-model">${escapeHtml(slot.aircraftModel)}</span>
          </span>
        </td>
        <td data-label="Book">
          <button class="row-action" type="button" data-slot-index="${index}">
            ${icons.book}
            Book
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function renderBookings(bookings) {
  if (bookings.length === 0) {
    bookingsList.innerHTML = `
      <div class="empty-state">
        <span class="empty-state-content">
          <strong>No active bookings</strong>
          <span>${escapeHtml(studentDisplayName())} has no lessons on the ledger.</span>
        </span>
      </div>
    `;
    return;
  }

  bookingsList.innerHTML = bookings.map(booking => {
    const range = formatTimeRange(booking.startLocal, booking.endLocal);
    const cancelText = booking.canCancelSelfService ? 'Cancel booking' : 'Cancellation closed';
    return `
      <section class="booking">
        <div class="booking-row">
          <span class="booking-title">
            <strong>${escapeHtml(range.time)}</strong>
            <span class="booking-meta">${escapeHtml(range.date)}</span>
          </span>
          <span class="booking-chip">${escapeHtml(booking.status)}</span>
        </div>
        <p class="booking-detail">${escapeHtml(booking.instructorName)} / ${escapeHtml(booking.tailNumber)} / ${escapeHtml(booking.aircraftModel)}</p>
        <p class="booking-detail">Cancel by ${escapeHtml(formatDeadline(booking.cancelDeadlineUtc))}</p>
        <button class="booking-action" type="button" data-cancel="${escapeHtml(booking.id)}" ${booking.canCancelSelfService ? '' : 'disabled'}>
          ${icons.cancel}
          ${cancelText}
        </button>
      </section>
    `;
  }).join('');
}

async function loadRoster() {
  const [health, studentsPayload, instructorsPayload, aircraftPayload] = await Promise.all([
    api('/api/health'),
    api('/api/students'),
    api('/api/instructors'),
    api('/api/aircraft')
  ]);

  state.students = studentsPayload.students || [];
  state.instructors = instructorsPayload.instructors || [];
  state.aircraft = aircraftPayload.aircraft || [];
  studentSelect.innerHTML = state.students
    .map(student => `<option value="${escapeHtml(student.id)}">${escapeHtml(student.name)}</option>`)
    .join('');
  instructorFilter.innerHTML = [
    '<option value="all">All instructors</option>',
    ...state.instructors.map(instructor => (
      `<option value="${escapeHtml(instructor.id)}">${escapeHtml(instructor.name)}</option>`
    ))
  ].join('');
  aircraftFilter.innerHTML = [
    '<option value="all">All aircraft</option>',
    ...state.aircraft
      .filter(plane => Number(plane.active) !== 0)
      .map(plane => `<option value="${escapeHtml(plane.id)}">${escapeHtml(plane.tail_number || plane.tailNumber)}</option>`)
  ].join('');

  serviceMetric.textContent = health.ok ? 'Online' : 'Degraded';
  serviceMetricCard.classList.toggle('is-online', Boolean(health.ok));
  serviceMetricCard.classList.toggle('is-offline', !health.ok);
  updateSummary();
}

async function loadAvailability() {
  const params = new URLSearchParams({
    date: dateInput.value,
    student_id: selectedStudentId()
  });
  const payload = await api(`/api/availability?${params}`);
  state.slots = payload.slots || [];
  renderFilteredAvailability();
}

async function loadBookings() {
  const params = new URLSearchParams({ student_id: selectedStudentId() });
  const payload = await api(`/api/bookings?${params}`);
  state.bookings = payload.bookings || [];
  renderBookings(state.bookings);
}

async function refresh() {
  if (!studentSelect.value || !dateInput.value) return;
  setMessage('');
  setBusy(true);
  renderAvailabilityLoading();
  renderBookingsLoading();
  try {
    await Promise.all([loadAvailability(), loadBookings()]);
  } catch (error) {
    setMessage(error.message, 'error');
  } finally {
    setBusy(false);
    updateSummary();
  }
}

function changeDay(offset) {
  const [year, month, day] = dateInput.value.split('-').map(Number);
  const current = year && month && day ? new Date(year, month - 1, day) : new Date();
  current.setDate(current.getDate() + offset);
  dateInput.value = toDateInputValue(current);
  refresh();
}

function setDateFromToday(offset) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  dateInput.value = toDateInputValue(date);
  refresh();
}

function resetFilters() {
  instructorFilter.value = 'all';
  aircraftFilter.value = 'all';
  state.filterWindow = 'all';
  segmentButtons.forEach(button => {
    button.classList.toggle('is-active', button.dataset.window === 'all');
  });
  renderFilteredAvailability();
}

document.addEventListener('click', event => {
  if (event.target.closest('#modalClose') || event.target === modal) {
    closeModal();
  }

  const testAction = event.target.closest('[data-action="run-tests"]');
  if (testAction) {
    event.preventDefault();
    (async () => {
      try {
        setMessage('Running local test suite...');
        const result = await api('/api/run-tests');
        setMessage(result.exit_code === 0 ? 'Tests completed.' : 'Tests completed with failures.', result.exit_code === 0 ? 'success' : 'error');
        showModal('Test output', result.output || '');
      } catch (error) {
        setMessage(error.message, 'error');
      }
    })();
  }
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
    closeModal();
  }
});

async function bookSlot(slot, button) {
  if (!slot) return;

  if (button) button.disabled = true;
  try {
    await api('/api/bookings', {
      method: 'POST',
      body: JSON.stringify({
        studentId: selectedStudentId(),
        instructorId: slot.instructorId,
        aircraftId: slot.aircraftId,
        startUtc: slot.startUtc
      })
    });
    setMessage('Lesson booked. Availability has been refreshed.', 'success');
    await refresh();
  } catch (error) {
    setMessage(error.message, 'error');
    await refresh();
  }
}

availabilityBody.addEventListener('click', async event => {
  const button = event.target.closest('button[data-slot-index]');
  if (!button) return;
  const slot = state.filteredSlots[Number(button.dataset.slotIndex)];
  await bookSlot(slot, button);
});

recommendationCard.addEventListener('click', async event => {
  const button = event.target.closest('button[data-recommendation-index]');
  if (!button) return;
  const slot = state.filteredSlots[Number(button.dataset.recommendationIndex)];
  await bookSlot(slot, button);
});

bookingsList.addEventListener('click', async event => {
  const button = event.target.closest('button[data-cancel]');
  if (!button) return;

  button.disabled = true;
  try {
    await api(`/api/bookings/${button.dataset.cancel}?student_id=${selectedStudentId()}`, {
      method: 'DELETE',
      body: JSON.stringify({ reason: 'student_requested' })
    });
    setMessage('Booking cancelled. The slot is available again.', 'success');
    await refresh();
  } catch (error) {
    setMessage(error.message, 'error');
    await refresh();
  }
});

loadButton.addEventListener('click', refresh);
studentSelect.addEventListener('change', refresh);
dateInput.addEventListener('change', refresh);
previousDayButton.addEventListener('click', () => changeDay(-1));
nextDayButton.addEventListener('click', () => changeDay(1));
quickDateButtons.forEach(button => {
  button.addEventListener('click', () => {
    setDateFromToday(Number(button.dataset.dateOffset));
  });
});
clearFiltersButton.addEventListener('click', resetFilters);
instructorFilter.addEventListener('change', renderFilteredAvailability);
aircraftFilter.addEventListener('change', renderFilteredAvailability);
segmentButtons.forEach(button => {
  button.addEventListener('click', () => {
    state.filterWindow = button.dataset.window;
    segmentButtons.forEach(item => {
      item.classList.toggle('is-active', item === button);
    });
    renderFilteredAvailability();
  });
});

document.addEventListener('DOMContentLoaded', async () => {
  dateInput.value = nextUsefulDate();
  renderAvailabilityLoading();
  renderBookingsLoading();

  try {
    await loadRoster();
    await refresh();
  } catch (error) {
    serviceMetric.textContent = 'Offline';
    serviceMetricCard.classList.add('is-offline');
    setMessage(error.message, 'error');
    updateSummary();
  }
});
