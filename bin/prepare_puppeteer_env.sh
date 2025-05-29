#!/bin/bash

# Store the original Puppeteer executable path
# Check if PUPPETEER_EXECUTABLE_PATH is undefined or set to an empty string
if [[ ! -z "${PUPPETEER_EXECUTABLE_PATH}" ]]; then
  export ORG_PUPPETEER_EXECUTABLE_PATH="$PUPPETEER_EXECUTABLE_PATH"
fi

# Set the PUPPETEER_EXECUTABLE_PATH to point to chrome-wrapper.sh in the same directory as this script
export PUPPETEER_EXECUTABLE_PATH="$(dirname "$0")/chrome-wrapper.sh"
