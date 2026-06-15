const fs = require('fs');

function extract() {
  const html = fs.readFileSync('cisco_raw.html', 'utf8');
  
  // Find "phApp" or "phApp = phApp ||"
  const startIdx = html.indexOf('var phApp = phApp ||');
  if (startIdx !== -1) {
    console.log('Found phApp start at:', startIdx);
    console.log(html.slice(startIdx, startIdx + 2500));
  } else {
    console.log('phApp not found');
  }
}

extract();
