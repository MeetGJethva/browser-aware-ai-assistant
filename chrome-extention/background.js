chrome.action.onClicked.addListener((tab) => {
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: [
      "highlighter.js",
      "price_tracker.js",
      "marked.min.js",
      "content.js",
      "youtube_chat.js",
    ],
  });
});
