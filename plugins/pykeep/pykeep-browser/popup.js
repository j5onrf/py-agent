document.getElementById("unlock-form").onsubmit = async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById("status");
  const pwdInput = document.getElementById("master-pwd");
  const masterPassword = pwdInput.value;
  pwdInput.value = ""; // Immediately wipe password from form

  statusEl.textContent = "Querying vault...";

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) {
    statusEl.textContent = "❌ No active webpage found.";
    return;
  }

  // Brave launches native_host.py directly via Native Messaging
  chrome.runtime.sendNativeMessage(
    "pykeep_host",
    { password: masterPassword, url: tab.url },
    async (response) => {
      if (chrome.runtime.lastError) {
        statusEl.textContent = "❌ " + chrome.runtime.lastError.message;
        return;
      }

      if (response.error) {
        statusEl.textContent = "❌ " + response.error;
        return;
      }

      if (!response.found) {
        statusEl.textContent = "❌ No matching entry for this site.";
        return;
      }

      // Inject directly into the webpage DOM
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "MAIN",
        args: [response.username, response.password],
        func: (user, pass) => {
          const passInput = document.querySelector('input[type="password"]');
          let userInput = document.querySelector('input[type="text"], input[type="email"], input[name*="user" i], input[name*="login" i]');

          if (!userInput && passInput && passInput.form) {
            const inputs = Array.from(passInput.form.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])'));
            const idx = inputs.indexOf(passInput);
            if (idx > 0) userInput = inputs[idx - 1];
          }

          if (userInput && user) {
            userInput.value = user;
            userInput.dispatchEvent(new Event("input", { bubbles: true }));
            userInput.dispatchEvent(new Event("change", { bubbles: true }));
          }

          if (passInput && pass) {
            passInput.value = pass;
            passInput.dispatchEvent(new Event("input", { bubbles: true }));
            passInput.dispatchEvent(new Event("change", { bubbles: true }));
          }
        }
      });

      // Done: close popup immediately; Python is already terminated
      window.close();
    }
  );
};
