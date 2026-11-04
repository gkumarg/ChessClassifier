const el = x => document.getElementById(x);

// File validation constants
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'];

function showPicker() {
  el("file-input").click();
}

function validateFile(file) {
  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    alert(`File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`);
    return false;
  }
  
  // Check file type
  if (!ALLOWED_TYPES.includes(file.type)) {
    alert('Please select a valid image file (JPEG, PNG, GIF, BMP, or WebP)');
    return false;
  }
  
  return true;
}

function showPicked(input) {
  if (!input.files || input.files.length === 0) {
    return;
  }
  
  const file = input.files[0];
  
  if (!validateFile(file)) {
    input.value = ''; // Clear the input
    return;
  }
  
  // Sanitize filename display
  const fileName = file.name.replace(/[<>]/g, '');
  el("upload-label").textContent = fileName;
  
  const reader = new FileReader();
  reader.onload = function(e) {
    el("image-picked").src = e.target.result;
    el("image-picked").className = "";
    el("result-label").textContent = ''; // Clear previous results
  };
  reader.onerror = function() {
    alert('Error reading file');
    input.value = '';
  };
  reader.readAsDataURL(file);
}

function analyze() {
  const uploadFiles = el("file-input").files;
  
  if (!uploadFiles || uploadFiles.length !== 1) {
    alert("Please select a file to analyze!");
    return;
  }
  
  const file = uploadFiles[0];
  if (!validateFile(file)) {
    return;
  }
  
  // Disable button during analysis
  const analyzeBtn = el("analyze-button");
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";
  el("result-label").textContent = "Processing...";
  
  const xhr = new XMLHttpRequest();
  
  // Set timeout for request
  xhr.timeout = 30000; // 30 seconds
  
  xhr.open("POST", "/analyze", true);
  
  xhr.onerror = function() {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
    el("result-label").textContent = "Error: Could not connect to server";
  };
  
  xhr.ontimeout = function() {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
    el("result-label").textContent = "Error: Request timed out";
  };
  
  xhr.onload = function(e) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
    
    if (this.readyState === 4) {
      try {
        const response = JSON.parse(e.target.responseText);
        
        if (this.status === 200) {
          // Success - display results (built from DOM nodes so response text is never parsed as HTML)
          const label = el("result-label");
          label.replaceChildren();
          const addLine = (title, value) => {
            const strong = document.createElement("strong");
            strong.textContent = title;
            label.append(strong, ` ${value}`);
          };

          addLine("Result:", response.result);

          if (response.confidence) {
            label.append(document.createElement("br"));
            addLine("Confidence:", response.confidence);
          }

          if (response.all_probabilities) {
            label.append(document.createElement("br"), document.createElement("br"));
            const heading = document.createElement("strong");
            heading.textContent = "All Probabilities:";
            const list = document.createElement("ul");
            list.className = "probabilities";
            for (const [piece, prob] of Object.entries(response.all_probabilities)) {
              const item = document.createElement("li");
              item.textContent = `${piece}: ${prob}`;
              list.append(item);
            }
            label.append(heading, list);
          }
        } else {
          // Error from server
          const errorMsg = response.error || 'An error occurred';
          el("result-label").textContent = `Error: ${errorMsg}`;
        }
      } catch (err) {
        el("result-label").textContent = "Error: Invalid response from server";
      }
    }
  };
  
  const fileData = new FormData();
  fileData.append("file", file);
  
  try {
    xhr.send(fileData);
  } catch (err) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
    el("result-label").textContent = "Error: Failed to send request";
  }
}

// Wire up event handlers (no inline handlers, so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', function() {
  el("choose-file-button").addEventListener('click', showPicker);
  el("analyze-button").addEventListener('click', analyze);
  el("file-input").addEventListener('change', function() { showPicked(this); });
});

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
  // Ctrl/Cmd + O to open file picker
  if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
    e.preventDefault();
    showPicker();
  }
  
  // Enter to analyze when file is selected
  if (e.key === 'Enter' && el("file-input").files.length > 0) {
    e.preventDefault();
    analyze();
  }
});