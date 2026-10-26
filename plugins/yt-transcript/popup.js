function formatTime(seconds) {
  const s = Math.floor(Number(seconds) || 0);
  const m = Math.floor(s / 60);
  const remainingS = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const remainingM = m % 60;
    return `${h}:${String(remainingM).padStart(2, '0')}:${String(remainingS).padStart(2, '0')}`;
  }
  return `${m}:${String(remainingS).padStart(2, '0')}`;
}

async function fetchAndProcessTranscript() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url || (!tab.url.includes('youtube.com/watch') && !tab.url.includes('youtube.com/shorts'))) {
    throw new Error('Please open a YouTube video first.');
  }

  const injectionResults = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: 'MAIN',
    func: async () => {
      const player = document.getElementById('movie_player') || document.getElementById('shorts-player');
      
      const urlParams = new URLSearchParams(window.location.search);
      let videoId = urlParams.get('v');
      if (!videoId) {
        const match = window.location.pathname.match(/\/shorts\/([a-zA-Z0-9_-]+)/);
        if (match) videoId = match[1];
      }
      if (!videoId && player?.getVideoData) {
        videoId = player.getVideoData().video_id;
      }

      if (!videoId) return { error: 'Could not find YouTube Video ID.' };

      const fetchCaptionData = async (url) => {
        let cleanUrl = url.replace(/&amp;/g, '&');
        let jsonUrl = cleanUrl.includes('fmt=')
          ? cleanUrl.replace(/fmt=[^&]+/, 'fmt=json3')
          : cleanUrl + (cleanUrl.includes('?') ? '&' : '?') + 'fmt=json3';

        try {
          const res = await fetch(jsonUrl);
          if (res.ok) {
            const text = await res.text();
            if (text && text.trim().length > 0) return text;
          }
        } catch (_) {}

        try {
          const res = await fetch(cleanUrl);
          if (res.ok) {
            const text = await res.text();
            if (text && text.trim().length > 0) return text;
          }
        } catch (_) {}

        return '';
      };

      const fetchInnerTubeTracks = async (clientName, clientVersion) => {
        try {
          const apiKey = window.ytcfg?.get?.('INNERTUBE_API_KEY') || '';
          const endpoint = apiKey ? `/youtubei/v1/player?key=${apiKey}` : '/youtubei/v1/player';
          const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              context: { client: { clientName, clientVersion } },
              videoId
            })
          });
          if (res.ok) {
            const data = await res.json();
            return data?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
          }
        } catch (_) {}
        return [];
      };

      let rawText = '';
      const response = player?.getPlayerResponse ? player.getPlayerResponse() : window.ytInitialPlayerResponse;
      const pageTracks = response?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
      const initialTrack = pageTracks.find(t => 
        (t.languageCode && t.languageCode.startsWith('en')) || 
        (t.vssId && t.vssId.includes('en'))
      ) || pageTracks[0];

      if (initialTrack && !initialTrack.baseUrl.includes('exp=xpe')) {
        rawText = await fetchCaptionData(initialTrack.baseUrl);
      }

      if (!rawText) {
        const androidTracks = await fetchInnerTubeTracks('ANDROID', '20.10.38');
        const aTrack = androidTracks.find(t => 
          (t.languageCode && t.languageCode.startsWith('en')) || 
          (t.vssId && t.vssId.includes('en'))
        ) || androidTracks[0];

        if (aTrack) rawText = await fetchCaptionData(aTrack.baseUrl);
      }

      if (!rawText) {
        const iosTracks = await fetchInnerTubeTracks('IOS', '20.10.4');
        const iTrack = iosTracks.find(t => 
          (t.languageCode && t.languageCode.startsWith('en')) || 
          (t.vssId && t.vssId.includes('en'))
        ) || iosTracks[0];

        if (iTrack) rawText = await fetchCaptionData(iTrack.baseUrl);
      }

      if (!rawText || !rawText.trim()) {
        return { error: 'No transcript found for this video.' };
      }

      const rawItems = [];

      // 1. JSON3
      try {
        const data = JSON.parse(rawText);
        if (data && Array.isArray(data.events)) {
          for (const ev of data.events) {
            if (!ev.segs) continue;
            const text = ev.segs.map(s => s.utf8 || '').join('').replace(/\s+/g, ' ').trim();
            if (text) {
              rawItems.push({ text, start: (ev.tStartMs || 0) / 1000 });
            }
          }
        }
      } catch (_) {}

      // 2. srv3 XML
      if (rawItems.length === 0) {
        const pRegex = /<p\b([^>]*)>([\s\S]*?)<\/p>/gi;
        let pMatch;
        while ((pMatch = pRegex.exec(rawText)) !== null) {
          const tMatch = pMatch[1].match(/\bt="(\d+)"/i);
          const start = tMatch ? parseInt(tMatch[1], 10) / 1000 : 0;
          let text = pMatch[2]
            .replace(/<[^>]+>/g, '')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#39;|&#x27;/g, "'")
            .replace(/&nbsp;/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
          if (text) rawItems.push({ text, start });
        }
      }

      // 3. Legacy XML
      if (rawItems.length === 0) {
        const textRegex = /<text\b([^>]*)>([\s\S]*?)<\/text>/gi;
        let textMatch;
        while ((textMatch = textRegex.exec(rawText)) !== null) {
          const startMatch = textMatch[1].match(/\bstart="([\d\.]+)"/i);
          const start = startMatch ? parseFloat(startMatch[1]) : 0;
          let text = textMatch[2]
            .replace(/<[^>]+>/g, '')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#39;|&#x27;/g, "'")
            .replace(/&nbsp;/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
          if (text) rawItems.push({ text, start });
        }
      }

      // Deduplicate consecutive lines
      const items = [];
      let prev = '';
      for (const item of rawItems) {
        if (item.text && item.text !== prev) {
          items.push(item);
          prev = item.text;
        }
      }

      if (items.length === 0) return { error: 'Could not parse transcript.' };
      return { items };
    }
  });

  const result = injectionResults?.[0]?.result;
  if (!result || result.error) throw new Error(result?.error || 'Failed to extract transcript.');
  return result.items;
}

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  const btnClean = document.getElementById('btnClean');
  const btnTimed = document.getElementById('btnTimed');

  // Hard off / Idle when opened
  statusEl.textContent = 'Click an option to copy:';

  const handleCopy = async (withTimestamps) => {
    btnClean.disabled = true;
    btnTimed.disabled = true;
    statusEl.textContent = 'Fetching transcript...';

    const label = withTimestamps ? 'Timestamped text' : 'Clean text';

    try {
      const items = await fetchAndProcessTranscript();
      let text = '';
      if (withTimestamps) {
        text = items.map(item => `[${formatTime(item.start)}] ${item.text}`).join('\n');
      } else {
        text = items.map(item => item.text).join(' ');
      }

      // Copy to clipboard
      await navigator.clipboard.writeText(text);

      // Calculate size statistics
      const wordCount = items.reduce((acc, item) => acc + item.text.split(/\s+/).filter(Boolean).length, 0);
      const kbSize = (new Blob([text]).size / 1024).toFixed(1);

      // Display both the label and the size loaded
      statusEl.textContent = `✅ ${label} copied! (~${wordCount.toLocaleString()} words · ${kbSize} KB)`;
    } catch (err) {
      statusEl.textContent = '❌ ' + err.message;
    } finally {
      btnClean.disabled = false;
      btnTimed.disabled = false;
    }
  };

  btnClean.onclick = () => handleCopy(false);
  btnTimed.onclick = () => handleCopy(true);
});
