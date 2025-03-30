"use client"

import { useState } from "react"
import MoodForm from "@/components/mood-form"
import PlaylistView from "@/components/playlist-view"
import { ThemeToggle } from "@/components/theme-toggle"
import type { Track } from "@/lib/types"

export default function Home() {
  const [view, setView] = useState<"input" | "playlist">("input")
  const [playlist, setPlaylist] = useState<Track[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [moodDescription, setMoodDescription] = useState("")
  const [spotifyPlaylistUrl, setSpotifyPlaylistUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)



  const handleBackToInput = () => {
    setView("input")
  }

  const handleMoodSubmit = async (moodText: string) => {
    setIsLoading(true)
    setError(null)
    
    try {
      // Call your Python script via the API route
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: moodText })
      });
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setPlaylist(data.tracks);
      setMoodDescription(moodText);
      setSpotifyPlaylistUrl(data.spotify_url);
      setView("playlist");
    } catch (err) {
      console.error("Error generating playlist:", err);
      setError(err instanceof Error ? err.message : "Failed to generate playlist");
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <main className="flex min-h-screen items-center justify-center p-6 bg-gradient-to-br from-purple-400 to-pink-400 dark:bg-slate-900">
      <div className="w-full max-w-md">
        <div className="overflow-hidden rounded-xl bg-white shadow-lg transition-all dark:bg-slate-800">
          <header className="flex justify-between items-start border-b border-gray-200 p-6 dark:border-gray-700">
            <div>
              <h1 className="text-2xl font-bold text-purple-500 mb-1">Moodify</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">Get personalized playlists based on your mood</p>
            </div>
            <ThemeToggle />
          </header>

          {error && (
            <div className="px-6 pt-4 -mb-2">
              <div className="p-3 bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400 rounded-md text-sm">
                {error}
              </div>
            </div>
          )}

          {view === "input" ? (
            <MoodForm onSubmit={handleMoodSubmit} isLoading={isLoading} />
          ) : (
            <PlaylistView
              tracks={playlist}
              moodDescription={moodDescription}
              spotifyPlaylistUrl={spotifyPlaylistUrl}
              onBack={handleBackToInput}
              onRegenerate={() => setView("input")}
            />
          )}
        </div>
      </div>
    </main>
  )
}

