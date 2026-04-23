<div align="center">

# ⚡ SYNAPSE

### **S**ystemic **N**exus of **A**daptive **P**rocessing & **S**elf-**E**xecution

A futuristic, cyberpunk-themed chat interface for AI agent communication

![React](https://img.shields.io/badge/React-19.1.0-61DAFB?style=flat-square&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=flat-square&logo=typescript)
![Vite](https://img.shields.io/badge/Vite-7.0-646CFF?style=flat-square&logo=vite)
![TailwindCSS](https://img.shields.io/badge/Tailwind-4.1-06B6D4?style=flat-square&logo=tailwindcss)
![Socket.IO](https://img.shields.io/badge/Socket.IO-4.8-010101?style=flat-square&logo=socket.io)

</div>

---

## 🌐 Overview

**SYNAPSE** is a sleek, cyberpunk-inspired real-time chat interface designed for communication with AI agents. Built with modern web technologies, it features stunning visual effects and smooth animations that create an immersive, futuristic experience.

## ✨ Features

### 🎨 Visual Experience
- **Matrix-Style Particle Background** — Animated falling characters (Katakana, Latin, numbers) creating a digital rain effect
- **Glassmorphism UI** — Frosted glass aesthetic with backdrop blur effects
- **Neon Glow Effects** — Cyan-themed glowing elements and drop shadows
- **Smooth Animations** — Fade-in transitions and responsive hover effects

### 💬 Chat Interface
- **Real-Time Messaging** — Powered by Socket.IO for instant communication
- **Scrambled Text Effect** — Agent responses appear with a cool decryption animation
- **Typing Indicator** — Pulsing dots show when the agent is processing
- **Auto-Scroll** — Chat automatically scrolls to the latest messages
- **Distinguished Messages** — Visual separation between user and agent messages

### 🔌 Connectivity
- **WebSocket Integration** — Real-time bidirectional communication
- **Connection Status** — Live indicator showing system online/offline status
- **Backend Ready** — Configured to connect to a backend server on `localhost:8000`

### 🖥️ User Interface
- **Entry Screen** — Cinematic landing page with the SYNAPSE title
- **Responsive Design** — Works on different screen sizes
- **Command Input** — Clean input bar with focus states

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **React 19** | UI Framework |
| **TypeScript** | Type Safety |
| **Vite 7** | Build Tool & Dev Server |
| **Tailwind CSS 4** | Styling |
| **Socket.IO Client** | Real-time Communication |

## 📁 Project Structure

```
synapse/
├── public/                  # Static assets
├── src/
│   ├── components/
│   │   ├── ChatDisplay.tsx      # Message display area
│   │   ├── EntryScreen.tsx      # Landing/splash screen
│   │   ├── InputBar.tsx         # Message input component
│   │   ├── ParticleBackground.tsx # Matrix rain effect
│   │   ├── ScrambledText.tsx    # Text decryption animation
│   │   └── TypingIndicator.tsx  # Agent typing animation
│   ├── hooks/
│   │   └── useScrambleEffect.ts # Custom hook for text scrambling
│   ├── App.tsx              # Main application component
│   ├── socket.ts            # Socket.IO configuration
│   ├── index.css            # Global styles
│   └── main.tsx             # Application entry point
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 🚀 Getting Started

### Prerequisites
- Node.js (v18 or higher recommended)
- npm or yarn
- A backend server running on `localhost:8000` (for Socket.IO)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd synapse
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the development server**
   ```bash
   npm run dev
   ```

4. **Open in browser**
   Navigate to `http://localhost:5173`

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## ⚙️ Configuration

### Backend Connection
To change the backend server URL, edit [src/socket.ts](src/socket.ts):

```typescript
const URL = 'http://localhost:8000'; // Change this to your backend URL
```

## 📜 Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |

## 🎮 Usage

1. **Launch** — Open the application to see the SYNAPSE entry screen
2. **Enter** — Click the `[ ENTER ]` button to access the chat interface
3. **Chat** — Type your message in the input bar and press Enter to send
4. **Observe** — Watch as agent responses decrypt with the scramble effect

---

<div align="center">

**[ SYNAPSE ]** — *Where human meets machine*

</div>
