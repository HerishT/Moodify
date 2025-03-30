"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import type { Track } from "@/lib/types"
import Image from "next/image"

interface PlaylistViewProps {
  tracks: Track[]
  moodDescription: string
  spotifyPlaylistUrl: string | null
  onBack: () => void
  onRegenerate: () => void
}

export default function PlaylistView({
  tracks,
  moodDescription,
  spotifyPlaylistUrl,
  onBack,
  onRegenerate,
}: PlaylistViewProps) {
  // Helper function to truncate text
  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + "..."
  }

  // Handle image error
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({})

  const handleImageError = (trackId: string) => {
    setImgErrors((prev) => ({
      ...prev,
      [trackId]: true,
    }))
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h2 className="text-xl font-semibold mb-2">Your Personalized Playlist</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Based on your mood: "{truncateText(moodDescription, 60)}"
        </p>
      </div>

      {tracks.length > 0 ? (
        <ul className="space-y-3 mb-6 max-h-[400px] overflow-y-auto pr-2">
          {tracks.map((track, index) => (
            <li
              key={track.id || index}
              className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg animate-in fade-in-0 slide-in-from-bottom-3 duration-300 flex items-center gap-3"
              style={{ animationDelay: `${(index + 1) * 100}ms` }}
            >
              <div className="flex-shrink-0 w-12 h-12 bg-gray-200 dark:bg-gray-600 rounded-md overflow-hidden">
                {track.albumImageUrl && !imgErrors[track.id] ? (
                  <Image
                    src={track.albumImageUrl || "/placeholder.svg"}
                    alt={track.album || "Album cover"}
                    width={48}
                    height={48}
                    className="object-cover w-full h-full"
                    onError={() => handleImageError(track.id)}
                    unoptimized // Skip image optimization for external URLs
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  </div>
                )}
              </div>
              <div className="flex-grow min-w-0">
                <div className="font-semibold mb-1 truncate">{track.name}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 truncate">{track.artists.join(", ")}</div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No tracks found for your mood. Try a different description.
        </div>
      )}

      {/* Spotify playlist button */}
      {spotifyPlaylistUrl && (
        <div className="mb-6">
          <a
            href={spotifyPlaylistUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center w-full p-3 bg-green-500 hover:bg-green-600 text-white rounded-md font-medium transition-colors"
          >
            <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
            </svg>
            Open in Spotify
          </a>
        </div>
      )}

      <div className="flex gap-3">
        <Button onClick={onBack} variant="outline" className="flex-1">
          Back
        </Button>
        <Button onClick={onRegenerate} className="flex-1 bg-purple-500 hover:bg-purple-600 text-white">
          Try Again
        </Button>
      </div>
    </div>
  )
}

