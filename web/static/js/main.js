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

  // Свои выпадающие списки вместо системных. Настоящий <select> остаётся в форме и отправляется как обычно.
  var openSelect = null;
  var closeOpenSelect = function () { if (openSelect) openSelect(false); };
  document.addEventListener("click", function (event) {
    if (openSelect && !event.target.closest(".cselect.is-open")) closeOpenSelect();
  });

  document.querySelectorAll("select:not([multiple]):not([disabled])").forEach(function (native, index) {
    var wrap = document.createElement("div");
    wrap.className = "cselect";
    native.parentNode.insertBefore(wrap, native);
    wrap.appendChild(native);
    native.classList.add("cselect-native");
    native.tabIndex = -1;
    native.setAttribute("aria-hidden", "true");

    var id = native.id || "cselect-" + index;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "cselect-btn";
    button.id = id + "-btn";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = "<span class=\"cselect-value\"></span><svg class=\"cselect-chev\" width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"m6 9 6 6 6-6\"/></svg>";
    var label = native.id && document.querySelector("label[for=\"" + native.id + "\"]");
    if (label) {
      label.htmlFor = button.id;
      if (!label.id) label.id = id + "-label";
      button.setAttribute("aria-labelledby", label.id + " " + button.id);
    }

    var list = document.createElement("ul");
    list.className = "cselect-list";
    list.id = id + "-list";
    list.setAttribute("role", "listbox");
    if (label) list.setAttribute("aria-labelledby", label.id);
    button.setAttribute("aria-controls", list.id);
    wrap.appendChild(button);
    wrap.appendChild(list);

    var items = Array.prototype.map.call(native.options, function (option, i) {
      var li = document.createElement("li");
      li.className = "cselect-option";
      li.id = id + "-opt-" + i;
      li.setAttribute("role", "option");
      li.textContent = option.textContent;
      li.addEventListener("click", function () { choose(i); });
      li.addEventListener("mousemove", function () { setActive(i); });
      list.appendChild(li);
      return li;
    });

    var active = -1;
    var setActive = function (i) {
      if (i < 0 || i >= items.length) return;
      if (items[active]) items[active].classList.remove("is-active");
      active = i;
      items[i].classList.add("is-active");
      button.setAttribute("aria-activedescendant", items[i].id);
      var top = items[i].offsetTop, bottom = top + items[i].offsetHeight;
      if (top < list.scrollTop) list.scrollTop = top;
      else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight;
    };
    var sync = function () {
      var i = native.selectedIndex;
      button.querySelector(".cselect-value").textContent = i >= 0 ? native.options[i].textContent : "";
      items.forEach(function (li, n) { li.setAttribute("aria-selected", String(n === i)); });
    };
    var setOpen = function (open) {
      if (open) {
        closeOpenSelect();
        var room = window.innerHeight - button.getBoundingClientRect().bottom;
        wrap.classList.toggle("is-up", room < 260 && button.getBoundingClientRect().top > room);
        openSelect = setOpen;
        setActive(Math.max(native.selectedIndex, 0));
      } else if (openSelect === setOpen) {
        openSelect = null;
      }
      wrap.classList.toggle("is-open", open);
      button.setAttribute("aria-expanded", String(open));
    };
    var choose = function (i) {
      var changed = native.selectedIndex !== i;
      native.selectedIndex = i;
      sync();
      setOpen(false);
      button.focus();
      if (changed) native.dispatchEvent(new Event("change", { bubbles: true }));
    };

    button.addEventListener("click", function () { setOpen(!wrap.classList.contains("is-open")); });
    // Фокус всегда остаётся на кнопке, стрелки двигают подсветку в списке.
    var typed = "", typedTimer;
    button.addEventListener("keydown", function (event) {
      var key = event.key;
      var open = wrap.classList.contains("is-open");
      if (!open) {
        if (["ArrowDown", "ArrowUp", "Enter", " "].indexOf(key) !== -1) { event.preventDefault(); setOpen(true); }
        return;
      }
      if (key === "ArrowDown") setActive(active + 1);
      else if (key === "ArrowUp") setActive(active - 1);
      else if (key === "Home") setActive(0);
      else if (key === "End") setActive(items.length - 1);
      else if (key === "Enter" || key === " ") choose(active);
      else if (key === "Escape") setOpen(false);
      else if (key === "Tab") { setOpen(false); return; }
      else if (key.length === 1) {
        // Быстрый переход по первым буквам: «а» → «Алматы».
        clearTimeout(typedTimer);
        typed += key.toLowerCase();
        typedTimer = setTimeout(function () { typed = ""; }, 600);
        var found = items.findIndex(function (li) { return li.textContent.toLowerCase().indexOf(typed) === 0; });
        if (found !== -1) setActive(found);
      } else return;
      event.preventDefault();
    });
    native.addEventListener("change", sync);
    if (native.form) native.form.addEventListener("reset", function () { setTimeout(sync); });
    sync();
  });

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
