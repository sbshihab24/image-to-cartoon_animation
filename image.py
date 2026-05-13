import os
import io
import sys
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from PIL import Image
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def cartoonize_image(input_path, output_path):
    """
    Cartoonizes an image using the gemini-3.1-flash-image-preview model.
    """
    # Initialize the Gemini Client with the API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return

    # Initialize the new Google GenAI Client
    client = genai.Client(api_key=api_key)

    # Load the input image
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    try:
        input_image = Image.open(input_path)
        # Ensure image is in a supported format (PNG/JPEG)
        if input_image.format not in ['PNG', 'JPEG']:
            # Convert to RGB if necessary
            input_image = input_image.convert('RGB')
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    # Define the prompt for cartoonization
    # Updated to a detailed 3D animated studio style (Pixar/Disney style)
    prompt = """
    A high-quality 3D animated character portrait, rendered in the
    distinctive aesthetic of a Pixar or Disney-style animated feature film.

    SUBJECT:
    A charming and optimized 3D avatar version of the person in the input image.
    While maintaining clear likeness and features (hair style, facial structure,
    skin tone), the appearance should be stylized to be symmetric, handsome,
    and appealing. Eyes should be large, expressive, and warm, with clean
    highlights. Skin should be smooth with soft subsurface scattering and
    minimized imperfections. Facial hair and hair should be clean, sculpted,
    and detailed with smooth textures.

    CLOTHING & POSE:
    Maintain the same pose and expression as the input image. The clothing
    should be a high-quality 3D rendered version of the original, preserving
    color and key details (like logos or patterns) with clean fabric fold patterns.

    ENVIRONMENT & LIGHTING:
    The background should be a clean, stylized 3D version of the original setting.
    Lighting should be soft, warm, and cinematic character lighting, with
    perfect key and fill lights to sculpt the face, creating clean highlights
    and soft shadows.

    Avoid:
    - Real-world photorealism
    - Gritty textures or imperfections
    - Flat 2D vector style
    - Anime style
    - Cartoon distortion
    - Rough, unpolished models
    """


    print(f"Cartoonizing '{input_path}' using gemini-3.1-flash-image-preview...")

    try:
        # Generate content with image output modality
        # This model supports multi-modal input and output
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt, input_image],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )

        # The response should contain the generated image in the inline_data parts
        image_saved = False
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data:
                        # Extract the image bytes
                        img_bytes = part.inline_data.data
                        cartoon_image = Image.open(io.BytesIO(img_bytes))
                        cartoon_image.save(output_path)
                        print(f"Successfully cartoonized! Saved to '{output_path}'")
                        image_saved = True
                        break
            if image_saved:
                break
        
        if not image_saved:
            print("No image was returned in the response.")
            if response.text:
                print(f"Model message: {response.text}")

    except Exception as e:
        print(f"An error occurred during generation: {e}")

if __name__ == "__main__":
    # Default paths
    input_img = "image_test.jpeg"
    output_img = "image_testoutput.png"
    
    # Allow passing input path as an argument
    if len(sys.argv) > 1:
        input_img = sys.argv[1]
    if len(sys.argv) > 2:
        output_img = sys.argv[2]

    cartoonize_image(input_img, output_img)
 