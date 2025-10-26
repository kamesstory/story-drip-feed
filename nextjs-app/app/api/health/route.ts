import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export async function GET() {
  const timestamp = new Date().toISOString();
  
  // Check if Supabase is configured
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  
  const health: {
    status: string;
    timestamp: string;
    database?: string;
    error?: string;
  } = {
    status: 'ok',
    timestamp,
  };

  // Try to check database connectivity if configured
  if (supabaseUrl && supabaseKey && supabaseUrl !== 'your-anon-key') {
    try {
      const supabase = createClient(supabaseUrl, supabaseKey);
      
      // Simple query to check connectivity
      const { error } = await supabase.from('stories').select('count', { count: 'exact', head: true });
      
      if (error) {
        // Table might not exist yet, which is OK during setup
        if (error.code === '42P01') {
          health.database = 'connected (tables not created)';
        } else {
          health.database = 'error';
          health.error = error.message;
        }
      } else {
        health.database = 'connected';
      }
    } catch (error) {
      health.database = 'error';
      health.error = error instanceof Error ? error.message : 'Unknown error';
    }
  } else {
    health.database = 'not configured';
  }

  return NextResponse.json(health);
}

