// app/api/generate/route.ts
import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export async function POST(request: Request) {
  try {
    const { text } = await request.json();
    
    if (!text || typeof text !== 'string') {
      return NextResponse.json(
        { error: "Valid text input is required" },
        { status: 400 }
      );
    }

    // Get absolute path to Python backend
    const backendPath = path.join(process.cwd(), 'backend/main.py');
    
    const pythonProcess = spawn('python3', [backendPath], {
      env: {
        ...process.env,
        USER_TEXT: text,
        PYTHONPATH: path.join(process.cwd(), 'backend')
      },
      cwd: process.cwd()
    });

    let outputData = '';
    let errorData = '';

    // Collect stdout data
    pythonProcess.stdout.on('data', (data) => {
      outputData += data.toString();
    });

    // Collect stderr data
    pythonProcess.stderr.on('data', (data) => {
      errorData += data.toString();
    });

    // Wait for process to exit
    const exitCode = await new Promise((resolve) => {
      pythonProcess.on('close', resolve);
    });

    if (exitCode !== 0 || errorData) {
      console.error('Python process error:', errorData);
      return NextResponse.json(
        { error: errorData || "Playlist generation failed" },
        { status: 500 }
      );
    }

    // Parse the Python output
    const result = JSON.parse(outputData);
    
    if (result.error) {
      return NextResponse.json(
        { error: result.error },
        { status: 500 }
      );
    }

    // Return the processed data
    return NextResponse.json(result);
  } catch (err) {
    console.error('API route error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Internal server error" },
      { status: 500 }
    );
  }
}
