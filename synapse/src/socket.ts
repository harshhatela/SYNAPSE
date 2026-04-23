import { io } from 'socket.io-client';

// The URL of your backend server
const URL = 'http://localhost:8000';

export const socket = io(URL);