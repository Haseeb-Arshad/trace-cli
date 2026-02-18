#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

// Extract arguments passed to the Node wrapper
const args = process.argv.slice(2);

// Execute the Python tracecli command
// We assume it's already installed via pip (pip install tracecli) 
// during the npm postinstall phase or manually.
const child = spawn('tracecli', args, {
    stdio: 'inherit',
    shell: true
});

child.on('error', (err) => {
    if (err.code === 'ENOENT') {
        console.error('\nError: tracecli (Python) not found.');
        console.error('Make sure you have Python installed and pip is in your PATH.');
        console.error('Try running: pip install tracecli\n');
    } else {
        console.error('\nError executing tracecli:', err.message);
    }
    process.exit(1);
});

child.on('close', (code) => {
    process.exit(code);
});
