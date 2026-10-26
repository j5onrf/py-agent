const IDLE_MINUTES = 10;

async function touchTab(tabId) {
  const { tabActivity = {} } = await chrome.storage.local.get("tabActivity");
  tabActivity[tabId] = Date.now();
  await chrome.storage.local.set({ tabActivity });
}

chrome.tabs.onActivated.addListener(({ tabId }) => {
  touchTab(tabId);
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const { tabActivity = {} } = await chrome.storage.local.get("tabActivity");
  delete tabActivity[tabId];
  await chrome.storage.local.set({ tabActivity });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url && tab.url.startsWith(chrome.runtime.getURL("suspend.html"))) {
    if (!tab.active && !tab.discarded) {
      chrome.tabs.discard(tabId);
    }
  }
});

// Setup Right-Click Menus cleanly with ["all"] context
function setupMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "suspend-current",
      title: "Suspend this tab",
      contexts: ["all"]
    });
    chrome.contextMenus.create({
      id: "suspend-background",
      title: "Suspend other tabs",
      contexts: ["all"]
    });
  });
}

chrome.runtime.onInstalled.addListener(setupMenus);
chrome.runtime.onStartup.addListener(setupMenus);
setupMenus();

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "suspend-current") {
    suspendTab(tab, true);
  } else if (info.menuItemId === "suspend-background") {
    suspendAllBackground();
  }
});

chrome.action.onClicked.addListener(suspendAllBackground);

async function suspendAllBackground() {
  const tabs = await chrome.tabs.query({ currentWindow: true });
  for (const tab of tabs) {
    if (!tab.active) suspendTab(tab);
  }
}

chrome.alarms.create("checkIdle", { periodInMinutes: 2 });
chrome.alarms.onAlarm.addListener(async () => {
  const { tabActivity = {} } = await chrome.storage.local.get("tabActivity");
  const tabs = await chrome.tabs.query({});
  const now = Date.now();
  let changed = false;

  for (const tab of tabs) {
    if (tab.active || tab.discarded) {
      if (tab.active) {
        tabActivity[tab.id] = now;
        changed = true;
      }
      continue;
    }

    if (!tabActivity[tab.id]) {
      tabActivity[tab.id] = now;
      changed = true;
      continue;
    }

    const idleTime = now - tabActivity[tab.id];
    if (idleTime > IDLE_MINUTES * 60 * 1000) {
      suspendTab(tab);
    }
  }

  if (changed) {
    await chrome.storage.local.set({ tabActivity });
  }
});

async function suspendTab(tab, force = false) {
  if (!force && (tab.active || tab.pinned || tab.audible || tab.discarded)) return;
  if (!tab.url || tab.url.startsWith("chrome://") || tab.url.startsWith("brave://") || tab.url.startsWith(chrome.runtime.getURL(""))) return;

  let finalUrl = tab.url;

  if (tab.url.includes("youtube.com/watch")) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const video = document.querySelector("video");
          return video ? Math.floor(video.currentTime) : null;
        }
      });

      const seconds = results?.[0]?.result;
      if (seconds && seconds > 5) {
        const urlObj = new URL(tab.url);
        urlObj.searchParams.set("t", `${seconds}s`);
        finalUrl = urlObj.toString();
      }
    } catch (e) {}
  }

  const suspendUrl = chrome.runtime.getURL("suspend.html") +
    "?url=" + encodeURIComponent(finalUrl) +
    "&title=" + encodeURIComponent(tab.title || "Suspended Tab");

  chrome.tabs.update(tab.id, { url: suspendUrl });
}
