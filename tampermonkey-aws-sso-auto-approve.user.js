// ==UserScript==
// @name         AWS SSO Auto-Approve for DogSTAC
// @namespace    https://github.com/dogstac
// @version      1.2.0
// @description  Auto-clicks "Confirm and continue" and "Allow access" on AWS SSO device authorization pages
// @match        https://*.awsapps.com/*
// @grant        window.close
// @run-at       document-start
// @updateURL    https://github.com/chanhyeokseo/dogstac/raw/refs/heads/main/tampermonkey-aws-sso-auto-approve.user.js
// @downloadURL  https://github.com/chanhyeokseo/dogstac/raw/refs/heads/main/tampermonkey-aws-sso-auto-approve.user.js
// ==/UserScript==

(function () {
  "use strict";

  const MAX_WAIT_MS = 10000;
  const POLL_INTERVAL_MS = 500;
  const CLOSE_DELAY_MS = 3000;
  const TAG = "[AWS SSO Auto-Approve]";

  function clickButton(button) {
    console.log(TAG, "Clicking:", button.textContent.trim());
    button.click();
  }

  function closeTab() {
    console.log(TAG, "Closing tab in", CLOSE_DELAY_MS, "ms");
    setTimeout(function () { window.close(); }, CLOSE_DELAY_MS);
  }

  function findButtonByText(text) {
    return Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent.trim().toLowerCase() === text.toLowerCase()
    );
  }

  function pollForButton(text, startTime, autoClose) {
    var btn = findButtonByText(text);
    if (btn && !btn.disabled) {
      clickButton(btn);
      if (autoClose) closeTab();
      return;
    }
    if (Date.now() - startTime < MAX_WAIT_MS) {
      setTimeout(function () { pollForButton(text, startTime, autoClose); }, POLL_INTERVAL_MS);
    } else {
      console.warn(TAG, "Timed out waiting for button:", text);
    }
  }

  function checkAndAct() {
    var hash = window.location.hash || "";
    var href = window.location.href || "";

    if (hash.includes("user_code=") || hash.includes("/device")) {
      console.log(TAG, "Device confirmation page detected:", href);
      pollForButton("Confirm and continue", Date.now());
    } else if (hash.includes("clientId=") || href.includes("clientId=")) {
      console.log(TAG, "Access grant page detected:", href);
      pollForButton("Allow access", Date.now(), true);
    }
  }

  console.log(TAG, "Script loaded on:", window.location.href);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", checkAndAct);
  } else {
    checkAndAct();
  }

  window.addEventListener("hashchange", function () {
    console.log(TAG, "Hash changed:", window.location.hash);
    checkAndAct();
  });

  var pushState = history.pushState;
  var replaceState = history.replaceState;
  history.pushState = function () {
    pushState.apply(this, arguments);
    console.log(TAG, "pushState:", window.location.href);
    setTimeout(checkAndAct, 300);
  };
  history.replaceState = function () {
    replaceState.apply(this, arguments);
    console.log(TAG, "replaceState:", window.location.href);
    setTimeout(checkAndAct, 300);
  };
})();
