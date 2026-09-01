/* i18n — loads translations from the backend and applies them to the DOM */

"use strict";

const I18N = (() => {
  let _lang = "en";
  let _map = {}; // { source: translation }

  /** Load translations for `lang` from the API. */
  async function load(lang) {
    _lang = lang || "en";
    if (_lang === "en") {
      _map = {};
      apply();
      return;
    }
    try {
      const res = await fetch(`/api/translations/${_lang}`);
      const data = await res.json();
      _map = data.translations || {};
    } catch (_) {
      _map = {};
    }
    apply();
  }

  /** Translate a source string. Returns the translation or the original. */
  function t(source) {
    return _map[source] || source;
  }

  /** Get the current language code. */
  function lang() {
    return _lang;
  }

  /** Apply translations to all elements with `data-i18n` attribute. */
  function apply() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) {
        const translated = t(key);
        // Preserve child elements with their own data-i18n
        if (el.children.length === 0) {
          el.textContent = translated;
        } else {
          // For elements with children, only update text nodes
          el.childNodes.forEach((node) => {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
              node.textContent = node.textContent.replace(
                /[^]*/,
                translated
              );
            }
          });
        }
      }
    });
    // Update placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.placeholder = t(key);
    });
    // Update titles
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) el.title = t(key);
    });
  }

  return { load, t, lang, apply };
})();
