"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Loader2 } from "lucide-react"

interface MoodFormProps {
  onSubmit: (moodText: string) => Promise<void>
  isLoading: boolean
}

export default function MoodForm({ onSubmit, isLoading }: MoodFormProps) {
  const [mood, setMood] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [mood])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!mood.trim()) {
      if (textareaRef.current) {
        textareaRef.current.focus()
      }
      return
    }

    await onSubmit(mood)
  }

  return (
    <div className="p-6">
      <form onSubmit={handleSubmit}>
        <div className="mb-6">
          <label htmlFor="mood-input" className="block font-medium mb-2">
            How are you feeling today?
          </label>
          <Textarea
            id="mood-input"
            ref={textareaRef}
            placeholder="e.g., I'm feeling energetic and ready to conquer the day!"
            value={mood}
            onChange={(e) => setMood(e.target.value)}
            className="resize-none min-h-[80px] w-full"
            disabled={isLoading}
          />
        </div>

        <Button type="submit" className="w-full bg-purple-500 hover:bg-purple-600 text-white" disabled={isLoading}>
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating Playlist...
            </>
          ) : (
            "Generate Playlist"
          )}
        </Button>
      </form>
    </div>
  )
}

