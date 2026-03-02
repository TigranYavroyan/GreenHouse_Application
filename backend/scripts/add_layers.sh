#!/bin/bash

set -e

echo "Adding controller.js and service.js to all subdirectories..."

for dir in */ ; do
    # remove trailing slash
    folder="${dir%/}"

    if [ -d "$folder" ]; then
        touch "$folder/controller.js"
        touch "$folder/service.js"
        echo "✔ Added to $folder"
    fi
done

echo "Done."