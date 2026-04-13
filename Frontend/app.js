const STORAGE_KEY = "ind_diplomat_chat_history_v2";
const MAX_CHATS = 40;
const DEFAULT_TITLE = "New strategic thread";

const API_SIMPLE_QUERY = "/api/simple/query";
const API_V2_QUERY = "/v2/query";
const API_HEALTH = "/health";
const API_MODEL = "/api/ollama";

const state = {
    chats: [],
    activeChatId: null,
    sending: false,
};

const elements = {
    historySidebar: document.getElementById("historySidebar"),
    historyList: document.getElementById("historyList"),
    workspaceTitle: document.getElementById("workspaceTitle"),
    chatFeed: document.getElementById("chatFeed"),
    emptyState: document.getElementById("emptyState"),
    promptInput: document.getElementById("promptInput"),
    composerForm: document.getElementById("composerForm"),
    sendBtn: document.getElementById("sendBtn"),
    newChatBtn: document.getElementById("newChatBtn"),
    clearChatBtn: document.getElementById("clearChatBtn"),
    historyToggle: document.getElementById("historyToggle"),
    screenBackdrop: document.getElementById("screenBackdrop"),
    countryInput: document.getElementById("countryInput"),
    apiStatus: document.getElementById("apiStatus"),
    modelStatus: document.getElementById("modelStatus"),
};

document.addEventListener("DOMContentLoaded", init);

function init() {
    bindEvents();
    restoreState();
    if (!state.chats.length) {
        createChat();
    }
    renderAll();
    resizeComposer();
    checkApiStatus();
    checkModelStatus();
}

function bindEvents() {
    elements.composerForm.addEventListener("submit", handleSubmit);
    elements.newChatBtn.addEventListener("click", () => {
        createChat();
        renderAll();
        focusPrompt();
    });

    elements.clearChatBtn.addEventListener("click", () => {
        const chat = getActiveChat();
        if (!chat) {
            return;
        }
        chat.messages = [];
        chat.title = DEFAULT_TITLE;
        chat.updatedAt = Date.now();
        persistState();
        renderAll();
        focusPrompt();
    });

    elements.promptInput.addEventListener("input", resizeComposer);
    elements.promptInput.addEventListener("keydown", handleComposerKeydown);

    elements.historyToggle.addEventListener("click", () => {
        document.body.classList.toggle("sidebar-open");
    });

    elements.screenBackdrop.addEventListener("click", () => {
        document.body.classList.remove("sidebar-open");
    });

    window.addEventListener("resize", resizeComposer);
}

function handleComposerKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        elements.composerForm.requestSubmit();
    }
}

function resizeComposer() {
    const input = elements.promptInput;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
}

function createChat() {
    const id = createId();
    state.chats.unshift({
        id,
        title: DEFAULT_TITLE,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messages: [],
    });
    state.activeChatId = id;

    if (state.chats.length > MAX_CHATS) {
        state.chats = state.chats.slice(0, MAX_CHATS);
    }

    persistState();
}

function setActiveChat(chatId) {
    state.activeChatId = chatId;
    persistState();
    renderAll();
    focusPrompt();
    document.body.classList.remove("sidebar-open");
}

function getActiveChat() {
    return state.chats.find((chat) => chat.id === state.activeChatId) || null;
}

async function handleSubmit(event) {
    event.preventDefault();

    if (state.sending) {
        return;
    }

    const prompt = elements.promptInput.value.trim();
    if (!prompt) {
        return;
    }

    const chat = getActiveChat();
    if (!chat) {
        return;
    }

    state.sending = true;
    elements.sendBtn.disabled = true;

    const userMessage = {
        id: createId(),
        role: "user",
        content: prompt,
        createdAt: Date.now(),
    };

    const pendingMessage = {
        id: createId(),
        role: "assistant",
        content: "Analyzing...",
        pending: true,
        createdAt: Date.now(),
    };

    chat.messages.push(userMessage, pendingMessage);
    chat.updatedAt = Date.now();

    if (chat.title === DEFAULT_TITLE) {
        chat.title = titleFromPrompt(prompt);
    }

    elements.promptInput.value = "";
    resizeComposer();

    persistState();
    renderAll();

    const countryCode = normalizeCountry(elements.countryInput.value);
    elements.countryInput.value = countryCode;

    try {
        const reply = await queryDiplomat(prompt, countryCode);

        pendingMessage.pending = false;
        pendingMessage.content = reply.answer || "No answer returned.";
        pendingMessage.meta = {
            outcome: reply.outcome,
            confidence: reply.confidence,
            risk: reply.riskLevel,
            traceId: reply.traceId,
        };

        chat.updatedAt = Date.now();
        setApiStatus(true, "API: online");
    } catch (error) {
        pendingMessage.pending = false;
        pendingMessage.content = `Request failed: ${error.message}`;
        pendingMessage.meta = null;
        chat.updatedAt = Date.now();
        setApiStatus(false, "API: offline");
    } finally {
        state.sending = false;
        elements.sendBtn.disabled = false;
        persistState();
        renderAll();
        focusPrompt();
    }
}

async function queryDiplomat(query, countryCode) {
    const payload = {
        query,
        country_code: countryCode,
    };

    try {
        const simpleResponse = await fetch(API_SIMPLE_QUERY, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (simpleResponse.ok) {
            const data = await simpleResponse.json();
            return normalizeApiReply(data);
        }
    } catch (error) {
        console.warn("Simple endpoint unavailable, fallback to v2.", error);
    }

    const v2Response = await fetch(API_V2_QUERY, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (!v2Response.ok) {
        let errorMessage = `HTTP ${v2Response.status}`;
        try {
            const err = await v2Response.json();
            errorMessage = err.error || errorMessage;
        } catch {
            // Keep default message.
        }
        throw new Error(errorMessage);
    }

    const data = await v2Response.json();
    return normalizeApiReply(data);
}

function normalizeApiReply(data) {
    return {
        answer: String(data.answer || "").trim(),
        outcome: String(data.outcome || "UNKNOWN"),
        confidence: toNumber(data.confidence),
        riskLevel: String(data.risk_level || "N/A"),
        traceId: String(data.trace_id || ""),
    };
}

function renderAll() {
    renderHistory();
    renderMessages();
    updateWorkspaceTitle();
}

function renderHistory() {
    const chats = [...state.chats].sort((a, b) => b.updatedAt - a.updatedAt);

    if (!chats.length) {
        elements.historyList.innerHTML = "<li class=\"history-empty\">No chats yet.</li>";
        return;
    }

    elements.historyList.innerHTML = "";

    for (const chat of chats) {
        const item = document.createElement("li");
        item.className = `history-item${chat.id === state.activeChatId ? " active" : ""}`;
        item.dataset.id = chat.id;

        const title = document.createElement("p");
        title.className = "history-title";
        title.textContent = chat.title;

        const meta = document.createElement("p");
        meta.className = "history-meta";
        meta.textContent = `${chat.messages.length} msg | ${formatRelativeTime(chat.updatedAt)}`;

        item.appendChild(title);
        item.appendChild(meta);

        item.addEventListener("click", () => setActiveChat(chat.id));
        elements.historyList.appendChild(item);
    }
}

function renderMessages() {
    const chat = getActiveChat();
    elements.chatFeed.innerHTML = "";

    if (!chat || !chat.messages.length) {
        elements.chatFeed.appendChild(elements.emptyState);
        return;
    }

    for (const message of chat.messages) {
        const row = document.createElement("article");
        row.className = `message ${message.role}`;

        const bubble = document.createElement("div");
        bubble.className = `bubble${message.pending ? " loading" : ""}`;
        bubble.textContent = message.content;

        if (message.meta && message.role === "assistant") {
            const meta = document.createElement("div");
            meta.className = "message-meta";
            const segments = [];
            if (message.meta.outcome) {
                segments.push(`Outcome: ${message.meta.outcome}`);
            }
            if (typeof message.meta.confidence === "number") {
                segments.push(`Confidence: ${Math.round(message.meta.confidence * 100)}%`);
            }
            if (message.meta.risk) {
                segments.push(`Risk: ${message.meta.risk}`);
            }
            if (message.meta.traceId) {
                segments.push(`Trace: ${message.meta.traceId}`);
            }
            meta.textContent = segments.join(" | ");
            bubble.appendChild(meta);
        }

        row.appendChild(bubble);
        elements.chatFeed.appendChild(row);
    }

    elements.chatFeed.scrollTop = elements.chatFeed.scrollHeight;
}

function updateWorkspaceTitle() {
    const chat = getActiveChat();
    elements.workspaceTitle.textContent = chat ? chat.title : DEFAULT_TITLE;
}

function focusPrompt() {
    elements.promptInput.focus();
}

async function checkApiStatus() {
    try {
        const response = await fetch(API_HEALTH);
        setApiStatus(response.ok, response.ok ? "API: online" : "API: degraded");
    } catch {
        setApiStatus(false, "API: offline");
    }
}

async function checkModelStatus() {
    try {
        const response = await fetch(API_MODEL);
        if (!response.ok) {
            setModelStatus(false, "Model: unknown");
            return;
        }

        const data = await response.json();
        if (data.ok) {
            const name = String(data.model || "ready").split(",")[0];
            setModelStatus(true, `Model: ${name}`);
        } else {
            setModelStatus(false, "Model: unavailable");
        }
    } catch {
        setModelStatus(false, "Model: unavailable");
    }
}

function setApiStatus(isOnline, text) {
    elements.apiStatus.textContent = text;
    elements.apiStatus.classList.toggle("online", isOnline);
    elements.apiStatus.classList.toggle("offline", !isOnline);
}

function setModelStatus(isOnline, text) {
    elements.modelStatus.textContent = text;
    elements.modelStatus.classList.toggle("online", isOnline);
    elements.modelStatus.classList.toggle("offline", !isOnline);
}

function restoreState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return;
        }

        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed.chats)) {
            return;
        }

        state.chats = parsed.chats
            .map((chat) => ({
                id: String(chat.id || createId()),
                title: String(chat.title || DEFAULT_TITLE),
                createdAt: Number(chat.createdAt || Date.now()),
                updatedAt: Number(chat.updatedAt || Date.now()),
                messages: Array.isArray(chat.messages)
                    ? chat.messages.map((message) => ({
                        id: String(message.id || createId()),
                        role: message.role === "assistant" ? "assistant" : "user",
                        content: String(message.content || ""),
                        meta: message.meta && typeof message.meta === "object" ? message.meta : null,
                        pending: false,
                        createdAt: Number(message.createdAt || Date.now()),
                    }))
                    : [],
            }))
            .slice(0, MAX_CHATS);

        const chatExists = state.chats.some((chat) => chat.id === parsed.activeChatId);
        state.activeChatId = chatExists ? parsed.activeChatId : state.chats[0]?.id || null;
    } catch (error) {
        console.warn("Failed to restore local chat history.", error);
    }
}

function persistState() {
    const payload = {
        activeChatId: state.activeChatId,
        chats: state.chats.slice(0, MAX_CHATS).map((chat) => ({
            ...chat,
            messages: chat.messages
                .filter((message) => !message.pending)
                .map((message) => ({
                    id: message.id,
                    role: message.role,
                    content: message.content,
                    meta: message.meta || null,
                    createdAt: message.createdAt,
                })),
        })),
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function normalizeCountry(value) {
    const normalized = String(value || "UNKNOWN")
        .toUpperCase()
        .replace(/[^A-Z]/g, "")
        .slice(0, 5);

    return normalized || "UNKNOWN";
}

function titleFromPrompt(prompt) {
    const compact = prompt.replace(/\s+/g, " ").trim();
    return compact.length > 48 ? `${compact.slice(0, 48)}...` : compact;
}

function formatRelativeTime(timestamp) {
    const deltaSeconds = Math.max(1, Math.floor((Date.now() - timestamp) / 1000));

    if (deltaSeconds < 60) {
        return `${deltaSeconds}s ago`;
    }

    const deltaMinutes = Math.floor(deltaSeconds / 60);
    if (deltaMinutes < 60) {
        return `${deltaMinutes}m ago`;
    }

    const deltaHours = Math.floor(deltaMinutes / 60);
    if (deltaHours < 24) {
        return `${deltaHours}h ago`;
    }

    const deltaDays = Math.floor(deltaHours / 24);
    return `${deltaDays}d ago`;
}

function toNumber(value) {
    const num = Number(value);
    return Number.isFinite(num) ? Math.max(0, Math.min(1, num)) : null;
}

function createId() {
    return `chat_${Math.random().toString(36).slice(2, 11)}_${Date.now().toString(36)}`;
}
