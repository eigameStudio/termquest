# TermQuest by eigamestudio

Welcome! This repository contains the script files for our multiplayer game network logic. 

## ⚠️ Strict Licensing Rules
You are permitted to modify and use this code for your own games, but you must follow these rules under penalty of law:

1. **No Adult Content:** You cannot use this code to create, modify, or host sexually explicit or "sus" materials.
2. **No Illegal Activities:** You cannot use this code for hacking, malware, scams, or any illegal network operations.

Breaking any of these rules immediately and automatically revokes your right to use the code. 

**eigamestudio** will aggressively issue DMCA takedowns and protect our brand against any violating projects hosted on GitHub, itch.io, Discord, or other platforms.

## 🛠️ Project Status: Alpha / Work-in-Progress
Please note that this project is **not complete** and is currently under active development. 
* You **will** encounter bugs, network glitches, or crashes.
* Features may change or be removed at any time.

### ⚠️ Known Issues
* **Chunk Generation / Missing Blocks:** You might see holes in the map or blocks rendering out of order. This is a known multiplayer sync glitch we are currently fixing. If your screen looks broken, try disconnecting and reconnecting to the server.

### 🚀 Getting Started
* **termquest.v1.py**: Handles player connection, sending inputs, and receiving server data.
* **termquestserver.v1.py**: Handles incoming player connections, game state updates, and broadcasting data.
