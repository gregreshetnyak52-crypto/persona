// Telegram WebApp SDK может отсутствовать при открытии страницы в обычном
// браузере (для визуальной отладки вне Telegram) — подменяем заглушкой.
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : {
  ready() {}, expand() {}, close() {}, initData: "",
  MainButton: {
    show() {}, hide() {}, setText() {}, onClick() {}, offClick() {}, setParams() {},
    disable() {}, enable() {}, showProgress() {}, hideProgress() {},
  },
  BackButton: { show() {}, hide() {}, onClick() {}, offClick() {} },
  HapticFeedback: { impactOccurred() {}, notificationOccurred() {} },
  themeParams: {},
};

tg.ready();
tg.expand();

const SCREEN_ORDER = ["categories", "services", "masters", "calendar", "times", "contact", "confirm", "result"];
const MONTH_NAMES = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const WEEKDAY_INDEX = [6, 0, 1, 2, 3, 4, 5]; // getDay() 0=Вс -> позиция в сетке Пн..Вс

const state = {
  category: null,
  service: null,
  master: null,
  availableDates: [],
  calendarMonth: null,
  date: null,
  timeSlot: null,
  name: "",
  phone: "",
};

let screenStack = ["categories"];
let bookingInFlight = false;
const mainBtn = tg.MainButton;

function currentScreen() {
  return screenStack[screenStack.length - 1];
}

function showScreen(name, { back = false, push = true } = {}) {
  if (push) screenStack.push(name);
  document.querySelectorAll(".screen").forEach((el) => {
    const isTarget = el.dataset.screen === name;
    el.classList.toggle("active", isTarget);
    el.classList.toggle("back", isTarget && back);
  });
  const idx = SCREEN_ORDER.indexOf(name);
  document.getElementById("progress-bar").style.width = `${((idx + 1) / SCREEN_ORDER.length) * 100}%`;

  if (screenStack.length > 1) tg.BackButton.show();
  else tg.BackButton.hide();

  updateMainButton();
}

function goBack() {
  if (screenStack.length <= 1) return;
  screenStack.pop();
  const prev = currentScreen();
  showScreen(prev, { back: true, push: false });
}

tg.BackButton.onClick(goBack);

function haptic(kind = "light") {
  tg.HapticFeedback.impactOccurred(kind);
}

// ── MainButton управляет переходом вперёд на экранах формы/подтверждения ──

function updateMainButton() {
  const screen = currentScreen();
  if (screen === "contact") {
    mainBtn.setText("Продолжить");
    mainBtn.show();
    mainBtn.offClick(onSubmitContact);
    mainBtn.onClick(onSubmitContact);
  } else if (screen === "confirm") {
    bookingInFlight = false;
    mainBtn.setText("Подтвердить запись");
    mainBtn.show();
    mainBtn.enable();
    mainBtn.hideProgress();
    mainBtn.offClick(onConfirmBooking);
    mainBtn.onClick(onConfirmBooking);
  } else {
    mainBtn.hide();
  }
}

// ── 1. Категории ───────────────────────────────────────────────────────

async function loadCategories() {
  const list = document.getElementById("categories-list");
  list.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
  const categories = await Api.categories();
  list.innerHTML = "";
  categories.forEach((c) => {
    const el = document.createElement("div");
    el.className = "cat-card";
    const [emoji, ...rest] = c.label.split(" ");
    el.innerHTML = `<span class="emoji">${emoji}</span><span>${rest.join(" ")}</span>`;
    el.addEventListener("click", () => {
      haptic();
      state.category = c.id;
      state.service = null;
      loadServices(c.id);
      showScreen("services");
    });
    list.appendChild(el);
  });
}

// ── 2. Услуги ──────────────────────────────────────────────────────────

let allServicesCache = [];

function renderServices(services) {
  const list = document.getElementById("services-list");
  list.innerHTML = "";
  if (!services.length) {
    list.innerHTML = `<div class="empty-state">Ничего не найдено</div>`;
    return;
  }
  services.forEach((s) => {
    const row = document.createElement("div");
    row.className = "service-row";
    const price = s.price_min ? `от ${Number(s.price_min).toLocaleString("ru-RU")} ₽` : "";
    row.innerHTML = `<span class="service-title"></span><span class="service-price">${price}</span>`;
    row.querySelector(".service-title").textContent = s.title;
    row.addEventListener("click", () => {
      haptic();
      state.service = s;
      state.master = null;
      loadMasters(s.id);
      showScreen("masters");
    });
    list.appendChild(row);
  });
}

async function loadServices(category) {
  const list = document.getElementById("services-list");
  list.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
  allServicesCache = await Api.services(category);
  renderServices(allServicesCache);
}

document.getElementById("services-search").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  renderServices(
    q ? allServicesCache.filter((s) => s.title.toLowerCase().includes(q)) : allServicesCache
  );
});

// ── 3. Мастера ─────────────────────────────────────────────────────────

async function loadMasters(serviceId) {
  const list = document.getElementById("masters-list");
  const dots = document.getElementById("masters-dots");
  list.innerHTML = `<div class="skeleton" style="flex:0 0 82%;height:340px"></div>`;
  dots.innerHTML = "";
  const masters = await Api.masters(serviceId);
  list.innerHTML = "";
  masters.forEach((m, i) => {
    const card = document.createElement("div");
    card.className = "master-card";
    const photo = m.photo_url
      ? `<img class="master-photo" src="${m.photo_url}" alt="">`
      : `<div class="master-photo"></div>`;
    const exp = m.experience ? `Опыт: ${m.experience} ${yearsWord(m.experience)}` : "";
    card.innerHTML = `
      ${photo}
      <div class="master-body">
        <div class="master-name"></div>
        <div class="master-exp">${exp}</div>
        <div class="master-bio"></div>
        <div class="master-select-btn">Выбрать мастера</div>
      </div>`;
    card.querySelector(".master-name").textContent = m.name;
    card.querySelector(".master-bio").textContent = m.bio || "";
    card.querySelector(".master-select-btn").addEventListener("click", () => {
      haptic("medium");
      state.master = m;
      state.date = null;
      state.calendarMonth = null;
      loadDates();
      showScreen("calendar");
    });
    list.appendChild(card);

    const dot = document.createElement("div");
    dot.className = "dot" + (i === 0 ? " active" : "");
    dots.appendChild(dot);
  });

  list.addEventListener("scroll", () => {
    const cardWidth = list.firstElementChild ? list.firstElementChild.getBoundingClientRect().width + 14 : 1;
    const idx = Math.round(list.scrollLeft / cardWidth);
    dots.querySelectorAll(".dot").forEach((d, i) => d.classList.toggle("active", i === idx));
  });
}

function yearsWord(n) {
  if (n % 100 >= 11 && n % 100 <= 19) return "лет";
  const r = n % 10;
  if (r === 1) return "год";
  if (r >= 2 && r <= 4) return "года";
  return "лет";
}

// ── 4. Календарь ───────────────────────────────────────────────────────

async function loadDates() {
  const grid = document.getElementById("calendar-grid");
  grid.innerHTML = "";
  state.availableDates = await Api.dates(state.master.id, state.service.id);
  if (!state.availableDates.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">Нет свободных дат</div>`;
    return;
  }
  const first = state.availableDates[0];
  state.calendarMonth = new Date(first.slice(0, 4), Number(first.slice(5, 7)) - 1, 1);
  renderCalendar();
}

function renderCalendar() {
  const grid = document.getElementById("calendar-grid");
  const monthEl = document.getElementById("cal-month");
  const y = state.calendarMonth.getFullYear();
  const m = state.calendarMonth.getMonth();
  monthEl.textContent = `${MONTH_NAMES[m]} ${y}`;

  const availSet = new Set(state.availableDates);
  const minMonth = state.availableDates[0].slice(0, 7);
  const maxMonth = state.availableDates[state.availableDates.length - 1].slice(0, 7);
  const thisMonthKey = `${y}-${String(m + 1).padStart(2, "0")}`;
  document.getElementById("cal-prev").disabled = thisMonthKey <= minMonth;
  document.getElementById("cal-next").disabled = thisMonthKey >= maxMonth;

  grid.innerHTML = "";
  const firstDay = new Date(y, m, 1);
  const leadingEmpty = WEEKDAY_INDEX[firstDay.getDay()];
  for (let i = 0; i < leadingEmpty; i++) {
    const empty = document.createElement("div");
    empty.className = "cal-day empty";
    grid.appendChild(empty);
  }
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  for (let d = 1; d <= daysInMonth; d++) {
    const key = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const cell = document.createElement("div");
    cell.textContent = d;
    const available = availSet.has(key);
    cell.className = "cal-day " + (available ? "available" : "disabled");
    if (key === state.date) cell.classList.add("selected");
    if (available) {
      cell.addEventListener("click", () => {
        haptic();
        state.date = key;
        state.timeSlot = null;
        renderCalendar();
        loadTimes();
        showScreen("times");
      });
    }
    grid.appendChild(cell);
  }
}

document.getElementById("cal-prev").addEventListener("click", () => {
  state.calendarMonth.setMonth(state.calendarMonth.getMonth() - 1);
  renderCalendar();
});
document.getElementById("cal-next").addEventListener("click", () => {
  state.calendarMonth.setMonth(state.calendarMonth.getMonth() + 1);
  renderCalendar();
});

// ── 5. Время ───────────────────────────────────────────────────────────

async function loadTimes() {
  const list = document.getElementById("times-list");
  list.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
  const slots = await Api.times(state.master.id, state.service.id, state.date);
  list.innerHTML = "";
  if (!slots.length) {
    list.innerHTML = `<div class="empty-state" style="grid-column:1/-1">Нет свободного времени на эту дату</div>`;
    return;
  }
  slots.forEach((s) => {
    const el = document.createElement("div");
    el.className = "time-slot";
    el.textContent = s.time || (s.datetime || "").slice(11, 16);
    el.addEventListener("click", () => {
      haptic();
      document.querySelectorAll(".time-slot.selected").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      state.timeSlot = s;
      setTimeout(() => showScreen("contact"), 150);
    });
    list.appendChild(el);
  });
}

// ── 6. Контакты ────────────────────────────────────────────────────────

const NAME_RE = /^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\s-]{1,49}$/;

function normalizeRuPhone(raw) {
  let digits = raw.replace(/\D/g, "");
  if (digits.length === 10) digits = "7" + digits;
  if (digits.length !== 11 || !["7", "8"].includes(digits[0])) return null;
  if (digits[0] === "8") digits = "7" + digits.slice(1);
  return digits;
}

function onSubmitContact() {
  const nameInput = document.getElementById("input-name");
  const phoneInput = document.getElementById("input-phone");
  const errName = document.getElementById("error-name");
  const errPhone = document.getElementById("error-phone");
  errName.textContent = "";
  errPhone.textContent = "";
  nameInput.classList.remove("invalid");
  phoneInput.classList.remove("invalid");

  const name = nameInput.value.trim();
  const phone = normalizeRuPhone(phoneInput.value.trim());
  let ok = true;

  if (!NAME_RE.test(name)) {
    errName.textContent = "Введите имя буквами (например: Анна)";
    nameInput.classList.add("invalid");
    ok = false;
  }
  if (!phone) {
    errPhone.textContent = "Не удалось распознать номер";
    phoneInput.classList.add("invalid");
    ok = false;
  }
  if (!ok) {
    haptic("rigid");
    return;
  }

  state.name = name;
  state.phone = phone;
  renderSummary();
  showScreen("confirm");
}

// ── 7. Подтверждение ───────────────────────────────────────────────────

function renderSummary() {
  const card = document.getElementById("summary-card");
  const dt = state.timeSlot.datetime || "";
  const dateDisplay = state.date;
  const timeDisplay = state.timeSlot.time || dt.slice(11, 16);
  card.innerHTML = `
    <div class="row"><span class="label">Услуга</span><span class="value" id="s-service"></span></div>
    <div class="row"><span class="label">Мастер</span><span class="value" id="s-master"></span></div>
    <div class="row"><span class="label">Дата</span><span class="value">${dateDisplay}</span></div>
    <div class="row"><span class="label">Время</span><span class="value">${timeDisplay}</span></div>
    <div class="row"><span class="label">Имя</span><span class="value" id="s-name"></span></div>
    <div class="row"><span class="label">Телефон</span><span class="value">+${state.phone}</span></div>
  `;
  card.querySelector("#s-service").textContent = state.service.title;
  card.querySelector("#s-master").textContent = state.master.name;
  card.querySelector("#s-name").textContent = state.name;
}

async function onConfirmBooking() {
  // Защита от повторной отправки: без этого быстрый двойной тап по кнопке
  // (или пауза с зависшим первым запросом) уходит вторым POST /api/booking
  // на тот же слот — первый бронирует его, второй получает отказ от
  // YClients, и клиент видит подряд "успех" и "ошибку" по одной попытке.
  if (bookingInFlight) return;
  bookingInFlight = true;
  mainBtn.setText("Отправляю…");
  mainBtn.show();
  mainBtn.disable();
  mainBtn.showProgress(true);
  try {
    const result = await Api.book({
      init_data: tg.initData || "",
      service_id: state.service.id,
      service_name: state.service.title,
      staff_id: state.master.id,
      master_name: state.master.name,
      datetime: state.timeSlot.datetime,
      client_name: state.name,
      client_phone: state.phone,
    });
    showResult(result.success, result.message);
  } catch (e) {
    showResult(false, "Не удалось связаться с сервером. Попробуйте ещё раз.");
  } finally {
    mainBtn.hideProgress();
  }
}

// ── 8. Результат ───────────────────────────────────────────────────────

function showResult(success, message) {
  const box = document.getElementById("result-box");
  if (success) {
    tg.HapticFeedback.notificationOccurred("success");
    box.innerHTML = `
      <div class="result-icon">✅</div>
      <div class="result-title">Запись подтверждена!</div>
      <div class="result-text">Мы отправили детали записи вам в чат.<br>Ждём вас в салоне «Персона»!</div>
    `;
  } else {
    tg.HapticFeedback.notificationOccurred("error");
    box.innerHTML = `
      <div class="result-icon">😔</div>
      <div class="result-title">Не удалось записаться</div>
      <div class="result-text">${message || "Попробуйте ещё раз или позвоните нам напрямую."}</div>
    `;
  }
  showScreen("result");
  mainBtn.setText(success ? "Готово" : "Закрыть");
  mainBtn.show();
  mainBtn.enable();
  mainBtn.offClick(onConfirmBooking);
  mainBtn.offClick(closeApp);
  mainBtn.onClick(closeApp);
  tg.BackButton.hide();
}

function closeApp() {
  tg.close();
}

// ── Старт ──────────────────────────────────────────────────────────────

showScreen("categories", { push: false });
loadCategories();
