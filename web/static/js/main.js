// TOIIM — небольшие улучшения интерфейса. Сайт работает и без JavaScript.
(function () {
  "use strict";

  // Мобильное меню: кнопка открывает/закрывает, Escape закрывает.
  var toggle = document.querySelector("[data-menu-toggle]");
  var nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    var setOpen = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
    };
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && nav.classList.contains("is-open")) {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  // Фото появляются плавно; пока грузятся, виден скелетон.
  document.querySelectorAll("img[data-img]").forEach(function (img) {
    var done = function () { img.classList.add("is-loaded"); };
    if (img.complete) done(); else { img.addEventListener("load", done); img.addEventListener("error", done); }
  });

  // Уведомления: закрываются кнопкой или сами через 6 секунд.
  document.querySelectorAll("[data-toast]").forEach(function (toast) {
    var hide = function () {
      toast.classList.add("is-hiding");
      setTimeout(function () { toast.remove(); }, 300);
    };
    toast.querySelector("[data-toast-close]").addEventListener("click", hide);
    setTimeout(hide, 6000);
  });

  // Защита от двойной отправки формы: кнопка блокируется после первого нажатия.
  document.querySelectorAll("form[data-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type=submit]");
      if (!button) return;
      button.disabled = true;
      button.classList.add("is-loading");
      var label = button.querySelector("span");
      if (label && button.dataset.loadingText) label.textContent = button.dataset.loadingText;
    });
  });

  // На телефоне фильтры каталога свёрнуты по умолчанию.
  var filters = document.querySelector("[data-filters]");
  if (filters && window.matchMedia("(max-width: 960px)").matches) filters.removeAttribute("open");

  // Кнопка «Оставить заявку» внизу экрана на телефоне прячется, когда форма уже видна.
  var mobileCta = document.querySelector(".mobile-cta");
  var requestBlock = document.getElementById("request");
  if (mobileCta && requestBlock && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      mobileCta.style.visibility = entries[0].isIntersecting ? "hidden" : "";
    }).observe(requestBlock);
  }

  // Калькулятор бюджета: считает сразу при вводе.
  var budget = document.querySelector("[data-budget]");
  if (budget) {
    var money = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
    var fmt = function (n) { return money.format(Math.round(n)) + " ₸"; };
    var labels = {
      menu: "Меню", venue: "Зал", host: "Ведущий", music: "Музыка",
      photo: "Фото и видео", decor: "Декор", other: "Другое"
    };
    var num = function (name) {
      var value = Number(budget.elements[name].value);
      return Number.isFinite(value) && value > 0 ? value : 0;
    };
    var render = function () {
      var guests = Math.min(num("guests"), 5000);
      var items = {
        menu: guests * num("menu"), venue: num("venue"), host: num("host"), music: num("music"),
        photo: num("photo"), decor: num("decor"), other: num("other")
      };
      var total = Object.keys(items).reduce(function (sum, key) { return sum + items[key]; }, 0);
      budget.querySelector("[data-total]").textContent = fmt(total);
      budget.querySelector("[data-per-guest]").textContent = guests ? fmt(total / guests) : "—";
      var list = budget.querySelector("[data-breakdown]");
      list.innerHTML = "";
      Object.keys(items).forEach(function (key) {
        if (!items[key]) return;
        var share = total ? (items[key] / total) * 100 : 0;
        var li = document.createElement("li");
        li.innerHTML = "<span></span><strong></strong><span class=\"bar\"><span></span></span>";
        li.children[0].textContent = labels[key];
        li.children[1].textContent = fmt(items[key]);
        li.querySelector(".bar span").style.width = share.toFixed(1) + "%";
        list.appendChild(li);
      });
    };
    budget.addEventListener("input", render);
    budget.addEventListener("submit", function (event) { event.preventDefault(); });
    render();
  }
})();
