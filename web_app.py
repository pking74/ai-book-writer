"""
Flask web application for OpenTale
"""
import os
import json
from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context, flash, redirect
from config import get_config
from agents import BookAgents
import prompts
import re

app = Flask(__name__)
app.secret_key = 'ai-book-writer-secret-key'  # For session management

# Ensure book_output directory exists
os.makedirs('book_output/chapters', exist_ok=True)

# Initialize global variables
agent_config = get_config()

@app.route('/')
def index():
    """Render the home page"""
    return render_template('index.html')

@app.route('/world', methods=['GET'])
def world():
    """Display world theme or chat interface"""
    # GET request - show world page with existing theme if available
    world_theme = ''
    if os.path.exists('book_output/world.txt'):
        with open('book_output/world.txt', 'r') as f:
            world_theme = f.read().strip()
        session['world_theme'] = world_theme

    return render_template('world.html', world_theme=world_theme, topic=session.get('topic', ''))

@app.route('/world_chat', methods=['POST'])
def world_chat():
    """Handle ongoing chat for world building"""
    data = request.json
    user_message = data.get('message', '')
    chat_history = data.get('chat_history', [])
    topic = data.get('topic', '')

    # Save topic to session if available
    if topic:
        session['topic'] = topic

    # Initialize agents for world building
    book_agents = BookAgents(agent_config)
    agents = book_agents.create_agents(topic, 0)

    # Generate response using the direct chat method
    ai_response = book_agents.generate_chat_response(chat_history, topic, user_message)

    # Clean the response
    ai_response = ai_response.strip()

    return jsonify({
        'message': ai_response
    })

@app.route('/world_chat_stream', methods=['POST'])
def world_chat_stream():
    """Handle ongoing chat for world building with streaming response"""
    data = request.json
    user_message = data.get('message', '')
    chat_history = data.get('chat_history', [])
    topic = data.get('topic', '')

    # Save topic to session if available
    if topic:
        session['topic'] = topic

    # Initialize agents for world building
    book_agents = BookAgents(agent_config)
    agents = book_agents.create_agents(topic, 0)

    # Generate streaming response
    stream = book_agents.generate_chat_response_stream(chat_history, topic, user_message)

    def generate():
        # Send a heartbeat to establish the connection
        yield "data: {\"content\": \"\"}\n\n"

        # Iterate through the stream to get each chunk
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                # Send each token as it arrives
                yield f"data: {json.dumps({'content': content})}\n\n"

        # Send completion marker
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no'  # Disable buffering in Nginx if used
                    })

@app.route('/finalize_world', methods=['POST'])
def finalize_world():
    """Finalize the world setting based on chat history"""
    data = request.json
    chat_history = data.get('chat_history', [])
    topic = data.get('topic', '')

    # Initialize agents for world building
    book_agents = BookAgents(agent_config)
    agents = book_agents.create_agents(topic, 0)

    # Generate the final world setting using the direct method
    world_theme = book_agents.generate_final_world(chat_history, topic)

    # Clean and save world theme to session and file
    world_theme = world_theme.strip()
    world_theme = re.sub(r'\n+', '\n', world_theme.strip())

    session['world_theme'] = world_theme
    with open('book_output/world.txt', 'w') as f:
        f.write(world_theme)

    return jsonify({
        'world_theme': world_theme
    })

@app.route('/finalize_world_stream', methods=['POST'])
def finalize_world_stream():
    """Finalize the world setting based on chat history with streaming response"""
    data = request.json
    chat_history = data.get('chat_history', [])
    topic = data.get('topic', '')

    # Initialize agents for world building
    book_agents = BookAgents(agent_config)
    agents = book_agents.create_agents(topic, 0)

    # Generate the final world setting using streaming
    stream = book_agents.generate_final_world_stream(chat_history, topic)

    def generate():
        # Send a heartbeat to establish the connection
        yield "data: {\"content\": \"\"}\n\n"

        # Collect all chunks to save the complete response
        collected_content = []

        # Iterate through the stream to get each chunk
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                collected_content.append(content)
                # Send each token as it arrives
                yield f"data: {json.dumps({'content': content})}\n\n"

        # Combine all chunks for the complete content
        complete_content = ''.join(collected_content)

        # Clean and save world theme to session and file once streaming is complete
        world_theme = complete_content.strip()
        world_theme = re.sub(r'\n+', '\n', world_theme)

        session['world_theme'] = world_theme
        with open('book_output/world.txt', 'w') as f:
            f.write(world_theme)

        # Send completion marker
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no'
                    })

@app.route('/save_world', methods=['POST'])
def save_world():
    """Save edited world theme"""
    world_theme = request.form.get('world_theme')
    world_theme = world_theme.replace('\r\n', '\n')
    world_theme = re.sub(r'\n{2,}', '\n\n', world_theme)

    # Strip extra newlines at the beginning and normalize newlines
    world_theme = world_theme.strip()
    world_theme = re.sub(r'\n+', '\n', world_theme.strip())

    # Save to session
    session['world_theme'] = world_theme

    # Save to file
    with open('book_output/world.txt', 'w') as f:
        f.write(world_theme)

    return jsonify({'success': True})

@app.route('/characters', methods=['GET'])
def characters():
    """Display characters or character creation chat interface"""
    # GET request - show characters page with existing characters if available
    characters_content = ''
    if os.path.exists('book_output/characters.txt'):
        with open('book_output/characters.txt', 'r') as f:
            characters_content = f.read().strip()
        session['characters'] = characters_content

    # Load world theme from file if it exists
    world_theme = ''
    if os.path.exists('book_output/world.txt'):
        with open('book_output/world.txt', 'r') as f:
            world_theme = f.read().strip()
    # If not available from file, try from session
    else:
        world_theme = session.get('world_theme', '')

    return render_template('characters.html',
                           characters=characters_content,
                           world_theme=world_theme)

@app.route('/save_characters', methods=['POST'])
def save_characters():
    """Save edited characters"""
    characters_content = request.form.get('characters')
    characters_content = characters_content.replace('\r\n', '\n')
    characters_content = re.sub(r'\n{2,}', '\n\n', characters_content)

    # Strip extra newlines at the beginning and normalize newlines
    characters_content = characters_content.strip()

    # Save to session
    session['characters'] = characters_content

    # Save to file
    with open('book_output/characters.txt', 'w') as f:
        f.write(characters_content)

    return jsonify({'success': True})

@app.route('/outline', methods=['GET', 'POST'])
def outline():
    # Check if world theme and characters exist
    if not os.path.exists('book_output/world.txt'):
        flash('You need to create a world setting first.', 'warning')
        return redirect('/world')

    if not os.path.exists('book_output/characters.txt'):
        flash('You need to create characters first.', 'warning')
        return redirect('/characters')

    # Get world theme and characters
    with open('book_output/world.txt', 'r') as f:
        world_theme = f.read()

    with open('book_output/characters.txt', 'r') as f:
        characters = f.read()

    # GET request - just show the page
    outline_content = ''
    if os.path.exists('book_output/outline.txt'):
        with open('book_output/outline.txt', 'r') as f:
            outline_content = f.read()

    # Get chapter list if it exists
    chapters = []
    if os.path.exists('book_output/chapters.json'):
        with open('book_output/chapters.json', 'r') as f:
            chapters = json.load(f)

    return render_template('outline.html',
                           world_theme=world_theme,
                           characters=characters,
                           outline=outline_content,
                           chapters=chapters)

@app.route('/generate_chapters', methods=['POST'])
def generate_chapters():
    """Generate chapters structure from existing outline"""
    # Check if we have an outline
    if not os.path.exists('book_output/outline.txt'):
        return jsonify({'error': 'Outline not found. Please create an outline first.'})

    # Get the outline content
    with open('book_output/outline.txt', 'r') as f:
        outline_content = f.read()

    # Get the desired number of chapters
    num_chapters = int(request.form.get('num_chapters', 10))

    # Parse the outline into chapters
    chapters = parse_outline_to_chapters(outline_content, num_chapters)

    # Save chapters to session and file
    session['chapters'] = chapters
    with open('book_output/chapters.json', 'w') as f:
        json.dump(chapters, f, indent=2)

    return jsonify({'success': True, 'num_chapters': len(chapters)})

@app.route('/save_outline', methods=['POST'])
def save_outline():
    """Save edited outline and generate chapters structure"""
    outline_content = request.form.get('outline')
    outline_content = outline_content.replace('\r\n', '\n')
    outline_content = re.sub(r'\n{2,}', '\n\n', outline_content)

    # Strip extra newlines at the beginning and normalize newlines
    outline_content = outline_content.strip()

    # Save to session
    session['outline'] = outline_content

    # Save to file
    with open('book_output/outline.txt', 'w') as f:
        f.write(outline_content)

    # Generate and save chapters
    num_chapters = int(request.form.get('num_chapters', 10))
    chapters = parse_outline_to_chapters(outline_content, num_chapters)

    # Save chapters to session and file
    session['chapters'] = chapters
    with open('book_output/chapters.json', 'w') as f:
        json.dump(chapters, f, indent=2)

    return jsonify({'success': True, 'num_chapters': len(chapters)})

@app.route('/chapter/<int:chapter_number>', methods=['GET', 'POST'])
def chapter(chapter_number):
    """Generate or display a specific chapter"""
    chapters = session.get('chapters', [])

    # If no chapters in session, try to load from file
    if not chapters and os.path.exists('book_output/chapters.json'):
        with open('book_output/chapters.json', 'r') as f:
            chapters = json.load(f)
            session['chapters'] = chapters

    # Check if chapter exists
    chapter_data = None
    for ch in chapters:
        if ch['chapter_number'] == chapter_number:
            chapter_data = ch
            break

    if not chapter_data:
        return render_template('error.html', message=f"Chapter {chapter_number} not found")

    if request.method == 'POST':
        # Get any additional context from the chat interface
        additional_context = request.form.get('additional_context', '')

        # Generate chapter content
        world_theme = session.get('world_theme', '')
        if not world_theme and os.path.exists('book_output/world.txt'):
            with open('book_output/world.txt', 'r') as f:
                world_theme = f.read().strip()
                session['world_theme'] = world_theme

        characters = session.get('characters', '')
        if not characters and os.path.exists('book_output/characters.txt'):
            with open('book_output/characters.txt', 'r') as f:
                characters = f.read().strip()
                session['characters'] = characters

        outline = session.get('outline', '')
        if not outline and os.path.exists('book_output/outline.txt'):
            with open('book_output/outline.txt', 'r') as f:
                outline = f.read().strip()
                session['outline'] = outline

        # Get previous chapters context
        previous_context = ""
        if chapter_number > 1:
            prev_chapter_path = f'book_output/chapters/chapter_{chapter_number-1}.txt'
            if os.path.exists(prev_chapter_path):
                with open(prev_chapter_path, 'r') as f:
                    # Get a summary or the last few paragraphs
                    content = f.read()
                    previous_context = content[-1000:] if len(content) > 1000 else content

        # Initialize agents for chapter generation
        book_agents = BookAgents(agent_config, chapters)
        agents = book_agents.create_agents(world_theme, len(chapters))

        # Add the additional context from chat to the chapter prompt
        chapter_prompt = f"{chapter_data['prompt']}\n\n{additional_context}" if additional_context else chapter_data['prompt']

        # Generate the chapter
        chapter_content = book_agents.generate_content(
            "writer",
            prompts.CHAPTER_GENERATION_PROMPT.format(
                chapter_number=chapter_number,
                chapter_title=chapter_data['title'],
                chapter_outline=chapter_prompt,
                world_theme=world_theme,
                relevant_characters=characters,  # You might want to filter for relevant characters only
                scene_details="",  # This would be filled if scenes were generated first
                previous_context=previous_context
            )
        )

        # Clean and save chapter content
        chapter_content = chapter_content.strip()
        chapter_path = f'book_output/chapters/chapter_{chapter_number}.txt'
        with open(chapter_path, 'w') as f:
            f.write(chapter_content)

        return jsonify({'chapter_content': chapter_content})

    # GET request - show chapter page with existing content if available
    chapter_content = ''
    chapter_path = f'book_output/chapters/chapter_{chapter_number}.txt'
    if os.path.exists(chapter_path):
        with open(chapter_path, 'r') as f:
            chapter_content = f.read().strip()

    return render_template('chapter.html', 
                          chapter=chapter_data, 
                          chapter_content=chapter_content)

# Helper function to parse outline into chapters
def parse_outline_to_chapters(outline_content, num_chapters):
    """Parse the outline into a structured list of chapters"""
    # This is a placeholder - you would need to implement the actual parsing logic
    # For now, we'll create a simple structure
    chapters = []
    
    # Split the outline into sections (this is very simplistic)
    sections = outline_content.split('\n\n')
    
    # Calculate how many sections per chapter
    sections_per_chapter = max(1, len(sections) // num_chapters)
    
    for i in range(num_chapters):
        start_idx = i * sections_per_chapter
        end_idx = min(start_idx + sections_per_chapter, len(sections))
        
        # Get the sections for this chapter
        chapter_sections = sections[start_idx:end_idx]
        
        # Create a title from the first line if possible
        title = f"Chapter {i+1}"
        if chapter_sections and chapter_sections[0]:
            first_line = chapter_sections[0].split('\n')[0].strip()
            if first_line:
                title = first_line
        
        # Join the sections for the chapter prompt
        prompt = '\n\n'.join(chapter_sections)
        
        chapters.append({
            'chapter_number': i + 1,
            'title': title,
            'prompt': prompt
        })
    
    return chapters

if __name__ == '__main__':
    # Run the application on port 9000
    app.run(host='0.0.0.0', port=9000, debug=True)
