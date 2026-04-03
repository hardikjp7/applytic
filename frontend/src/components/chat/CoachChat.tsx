import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { chatWithCoach } from '../../lib/api'
import type { Message } from '../../App'

interface Props {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
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
  }, [messages])

  const send = async (message: string) => {
    if (!message.trim() || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setLoading(true)

    try {
      const res = await chatWithCoach(message)
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, something went wrong. Try again in a moment.',
      }])
    } finally {
      setLoading(false)
    }
  }

  const isInitialState = messages.length === 1

  return (
    <div className="flex flex-col h-full p-6">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-gray-900">AI Coach</h1>
        <p className="text-sm text-gray-400 mt-0.5">Powered by your actual application data</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
              msg.role === 'assistant' ? 'bg-brand-100' : 'bg-gray-100'
            }`}>
              {msg.role === 'assistant'
                ? <Bot size={14} className="text-brand-600" />
                : <User size={14} className="text-gray-500" />
              }
            </div>
            <div className={`max-w-lg rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'assistant'
                ? 'bg-white border border-gray-100 text-gray-800'
                : 'bg-brand-600 text-white'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center">
              <Bot size={14} className="text-brand-600" />
            </div>
            <div className="bg-white border border-gray-100 rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions — only show on initial state */}
      {isInitialState && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs px-3 py-1.5 border border-gray-200 rounded-full text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
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
