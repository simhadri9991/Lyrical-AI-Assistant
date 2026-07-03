from django.shortcuts import render
from google import genai
from google.genai import types
import json
import os

def dashboard(request):
    # Initialize daily credits in browser session if it doesn't exist yet
    if 'daily_credits' not in request.session:
        request.session['daily_credits'] = 20

    # Prepare context with current credit balance
    context = {
        "credits_left": request.session['daily_credits']
    }
    
    if request.method == "POST":
        raw_lyrics = request.POST.get("lyrics")
        context["lyrics"] = raw_lyrics
        
        # 1. Check if user has ran out of credits locally
        if request.session['daily_credits'] <= 0:
            context.update({
                "error": "🚨 0 Credits Remaining! You have exhausted your daily allowance. Wait for a reset or clear your browser cookies to reset.",
                "processed": False
            })
            return render(request, "creator_tools/dashboard.html", context)
        
        # 2. Deduct 1 credit immediately and save session
        request.session['daily_credits'] -= 1
        request.session.modified = True
        context["credits_left"] = request.session['daily_credits']
        
        client = genai.Client()
        
        prompt = f"""
        You are an expert Music Historian and YouTube SEO Assistant.
        Analyze the following lyrics. 
        
        First, attempt to identify if these belong to a known, published song.
        If they do, extract the real song title, artist, release date, credits (writers/producers), and a brief thematic meaning.
        If they appear to be original or unknown, label the metadata fields as "Original / Unknown" but still provide a thematic meaning.
        
        Finally, determine the best musical vibe and generate the SEO and visual assets.
        
        Lyrics:
        {raw_lyrics}
        
        Return the result EXACTLY as a JSON object with the following keys:
        - "song_title": A string of the song name (or "Original Composition").
        - "artist": A string of the artist (or "Unknown").
        - "release_date": A string of the release date/year.
        - "credits": A string listing the main writers or producers.
        - "song_meaning": A 2-sentence summary of what the song is actually about.
        - "inferred_vibe": A string naming the exact mood/aesthetic.
        - "seo_description": A string containing the YouTube description and tags. CRITICAL REQUIREMENT: You MUST include a highly visible, dedicated "Credits & Attribution" section in this description text that explicitly lists the original performing artist, all known songwriters, lyricists, authors, and musical producers. You must also append their names into the metadata tags and hashtags at the bottom of the description text.
        - "visual_prompts": A list of 3 strings, each being a detailed Midjourney/Stable Diffusion prompt.
        - "timestamps": A string containing the formatted timestamp list.
        """
        
        safety_config = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]
        
        try:
            # Attempt 1: Try using the high-volume Flash-Lite model
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    safety_settings=safety_config,
                    response_mime_type="application/json",
                )
            )
            
            ai_data = json.loads(response.text)
            context.update({
                "ai_data": ai_data, 
                "processed": True
            })
            
        except Exception as e:
            error_msg = str(e)
            
            # AUTOMATED FALLBACK: If Lite is overloaded (503), immediately try standard Flash
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            safety_settings=safety_config,
                            response_mime_type="application/json",
                        )
                    )
                    ai_data = json.loads(response.text)
                    context.update({
                        "ai_data": ai_data, 
                        "processed": True
                    })
                    # Successfully recovered using fallback model, render the template now
                    return render(request, "creator_tools/dashboard.html", context)
                except Exception as fallback_error:
                    # If the fallback model also fails, catch its specific error instead
                    error_msg = str(fallback_error)

            # --- USER-FRIENDLY SYSTEM NOTIFICATIONS ---
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                friendly_error = "🚦 Free Tier Speed Limit! You are generating too fast. Please wait 15 seconds and try clicking the button again."
            elif "503" in error_msg or "UNAVAILABLE" in error_msg:
                friendly_error = "☁️ Google Servers are currently overloaded. Please wait a few seconds and try clicking the button again."
            else:
                friendly_error = f"System Error: {error_msg}"
                
            context.update({
                "error": friendly_error,
                "processed": False
            })
        
    return render(request, "creator_tools/dashboard.html", context)