#!/bin/bash
# Download MIT 6.006 Introduction to Algorithms (Fall 2011)
# Source: https://archive.org/details/MIT6.006F11
# License: CC BY-NC-SA 4.0
# Total: 24 lectures, ~5.3GB

set -e

BASE_URL="https://archive.org/download/MIT6.006F11"
TARGET_DIR="/home/turtle_wolfe/repos/OBS_bot/content/general/mit-6.006-algorithms"

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

echo "Downloading MIT 6.006 Introduction to Algorithms (24 lectures)..."
echo "Target directory: $TARGET_DIR"
echo ""

# Download all 24 lectures
wget -c "$BASE_URL/MIT6_006F11_lec01_300k.mp4" -O "01-Algorithmic_Thinking_Peak_Finding.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec02_300k.mp4" -O "02-Models_of_Computation_Document_Distance.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec03_300k.mp4" -O "03-Insertion_Sort_Merge_Sort.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec04_300k.mp4" -O "04-Heaps_and_Heap_Sort.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec05_300k.mp4" -O "05-Binary_Search_Trees_BST_Sort.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec06_300k.mp4" -O "06-AVL_Trees_AVL_Sort.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec07_300k.mp4" -O "07-Counting_Sort_Radix_Sort_Lower_Bounds.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec08_300k.mp4" -O "08-Hashing_with_Chaining.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec09_300k.mp4" -O "09-Table_Doubling_Karp_Rabin.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec10_300k.mp4" -O "10-Open_Addressing_Cryptographic_Hashing.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec11_300k.mp4" -O "11-Integer_Arithmetic_Karatsuba_Multiplication.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec12_300k.mp4" -O "12-Square_Roots_Newtons_Method.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec13_300k.mp4" -O "13-Breadth_First_Search_BFS.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec14_300k.mp4" -O "14-Depth_First_Search_DFS_Topological_Sort.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec15_300k.mp4" -O "15-Single_Source_Shortest_Paths.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec16_300k.mp4" -O "16-Dijkstra.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec17_300k.mp4" -O "17-Bellman_Ford.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec18_300k.mp4" -O "18-Speeding_up_Dijkstra.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec19_300k.mp4" -O "19-Dynamic_Programming_I.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec20_300k.mp4" -O "20-Dynamic_Programming_II.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec21_300k.mp4" -O "21-Dynamic_Programming_III.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec22_300k.mp4" -O "22-Dynamic_Programming_IV.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec23_300k.mp4" -O "23-Computational_Complexity.mp4"
wget -c "$BASE_URL/MIT6_006F11_lec24_300k.mp4" -O "24-Topics_in_Algorithms_Research.mp4"

echo ""
echo "Download complete! 24 lectures downloaded to $TARGET_DIR"
ls -lh "$TARGET_DIR" | wc -l
