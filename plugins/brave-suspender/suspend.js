const params = new URLSearchParams(window.location.search);
const targetUrl = params.get("url");
const targetTitle = params.get("title");

// Set exact website title without any changes
if (targetTitle) {
  document.title = targetTitle;
  const titleEl = document.getElementById("title");
  if (titleEl) titleEl.textContent = targetTitle;
}

// Pull real favicon directly from Brave and dim it to 40%
if (targetUrl) {
  const faviconApiUrl = chrome.runtime.getURL(`_favicon/?pageUrl=${encodeURIComponent(targetUrl)}&size=32`);
  const img = new Image();

  img.onload = () => {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth || 32;
      canvas.height = img.naturalHeight || 32;
      const ctx = canvas.getContext("2d");

      // Dim to 40% opacity (exact Marvellous Suspender style)
      ctx.globalAlpha = 0.4;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      const faviconLink = document.getElementById("favicon");
      if (faviconLink) {
        faviconLink.href = canvas.toDataURL("image/png");
      }
    } catch (e) {
      const faviconLink = document.getElementById("favicon");
      if (faviconLink) faviconLink.href = faviconApiUrl;
    }
  };

  img.src = faviconApiUrl;
}

function restore(e) {
  if (e) e.preventDefault();
  if (targetUrl) {
    window.location.href = targetUrl;
  }
}

if (targetUrl) {
  const link = document.getElementById("restore-link");
  if (link) {
    link.href = targetUrl;
    link.addEventListener("click", restore);
  }
}

document.addEventListener("click", restore);
document.addEventListener("keydown", restore);
