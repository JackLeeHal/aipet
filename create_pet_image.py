from PIL import Image, ImageDraw

def create_image():
    img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((10, 10, 90, 90), fill='red', outline='black')
    img.save('desktop_aipet/assets/pet.png')

if __name__ == "__main__":
    create_image()
