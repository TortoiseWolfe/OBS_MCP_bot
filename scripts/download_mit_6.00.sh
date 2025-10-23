#!/bin/bash
# Download MIT 6.00 Introduction to Computer Science and Programming (Fall 2008)
# Source: https://archive.org/details/MIT6.00F08
# License: CC BY-NC-SA 4.0
# Total: 24 lectures, ~2.6GB, ~20 hours

set -e

BASE_URL="https://archive.org/download/MIT6.00F08"
TARGET_DIR="/home/turtle_wolfe/repos/OBS_bot/content/general/mit-6.00-intro-cs"

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

echo "Downloading MIT 6.00 Introduction to Computer Science (24 lectures)..."
echo "Target directory: $TARGET_DIR"
echo ""

# Download all lectures
for i in $(seq -f "%02g" 1 24); do
    wget -c "$BASE_URL/MIT6_00F08_lec${i}_300k.mp4" -O "Lecture_${i}.mp4" || echo "Lecture $i may not exist, skipping..."
done

echo ""
echo "Download complete! Lectures downloaded to $TARGET_DIR"
ls -lh "$TARGET_DIR" | wc -l
