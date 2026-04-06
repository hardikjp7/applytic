import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { chatWithCoach } from '../../lib/api'
import type { Message } from '../../App'

interface Props {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

const INITIAL_MSG: Message = {
  role: 'assistant',
  content: "Hi! I'm your AI job search coach. I have access to your full application history and pattern data. Ask me anything — I'll give you specific advice based on your actual numbers.",
}

const SUGGESTIONS = [
  'Why am I getting ghosted after applying?',
  'Which source channel is working best for me?',
  'Should I tweak my resume version strategy?',
  'What should I focus on this week?',
]

export default function CoachChat({ messages, setMessages }: Props) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async (message: string) => {
    if (!message.trim() || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setLoading(true)
    try {
      const res = await chatWithCoach(message)
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }])
    } catch (err: any) {
      const msg = err?.response?.status === 429
        ? 'You have reached the daily limit of 20 messages. Come back tomorrow!'
        : 'Sorry, something went wrong. Try again in a moment.'
      setMessages(prev => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => setMessages([INITIAL_MSG])
  const isInitialState = messages.length === 1

  return (
    <div className="flex flex-col h-[calc(100vh-57px)] lg:h-screen p-4 lg:p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">AI Coach</h1>
          <p className="text-sm text-gray-400 mt-0.5">Powered by your actual application data</p>
        </div>
        {messages.length > 1 && (
          <button
            onClick={clearChat}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-red-500 border border-gray-200 dark:border-gray-700 hover:border-red-300 rounded-lg transition-colors"
          >
            <Trash2 size={12} /> Clear chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0 pr-1">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
              msg.role === 'assistant' ? 'bg-brand-100 dark:bg-brand-800/30' : 'bg-gray-100 dark:bg-gray-700'
            }`}>
              {msg.role === 'assistant'
                ? <Bot size={14} className="text-brand-600 dark:text-brand-400" />
                : <User size={14} className="text-gray-500 dark:text-gray-300" />
              }
            </div>
            <div className={`max-w-[85%] lg:max-w-lg rounded-2xl px-4 py-3 text-sm ${
              msg.role === 'assistant'
                ? 'bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 text-gray-800 dark:text-gray-100'
                : 'bg-brand-600 text-white'
            }`}>
              {msg.role === 'assistant' ? (
                <div className="markdown">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2.5">
            <div className="shrink-0 w-7 h-7 rounded-full bg-brand-100 dark:bg-brand-800/30 flex items-center justify-center">
              <Bot size={14} className="text-brand-600 dark:text-brand-400" />
            </div>
            <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl px-4 py-3">
              <div className="flex gap-1 items-center">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 bg-gray-300 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestion chips */}
      {isInitialState && (
        <div className="flex flex-wrap gap-2 mb-3 shrink-0">
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs px-3 py-1.5 border border-gray-200 dark:border-gray-700 rounded-full text-gray-500 dark:text-gray-400 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 shrink-0">
        <input
          className="flex-1 border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder:text-gray-400 dark:placeholder:text-gray-500"
          placeholder="Ask your coach anything..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
          disabled={loading}
        />
        <button
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          className="px-4 py-2.5 bg-brand-600 text-white rounded-xl hover:bg-brand-800 disabled:opacity-40 transition-colors"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}
