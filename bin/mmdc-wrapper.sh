#!/bin/bash

# prepare to chrome-wrapper.sh
. $(dirname "$0")/prepare_puppeteer_env.sh

# Pass all arguments from shell script to mmdc
$(dirname "$0")/node_modules/.bin/mmdc "$@"
