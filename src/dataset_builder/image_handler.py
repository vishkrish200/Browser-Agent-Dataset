'''
Module for handling image-related operations in the dataset builder.
'''

from typing import Optional, Tuple

class ImageHandler:
    '''Handles downloading, processing, and storing images.'''

    def __init__(self, storage_path: str = "./data/images"):
        self.storage_path = storage_path
        # Ensure storage_path exists, or create it
        # For example: os.makedirs(self.storage_path, exist_ok=True)
        print(f"Image storage path: {self.storage_path}")

    def download_image(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        '''Downloads an image from a given URL.

        Args:
            url: The URL of the image to download.
            filename: Optional filename to save the image as. 
                      If None, a filename will be generated.

        Returns:
            The path to the downloaded image, or None if download failed.
        '''
        # Placeholder for image download logic (e.g., using requests or httpx)
        print(f"Downloading image from {url}...")
        # Example: 
        # try:
        #     response = requests.get(url, stream=True)
        #     response.raise_for_status()
        #     # Determine filename, save file
        #     # return saved_filepath
        # except requests.RequestException as e:
        #     print(f"Error downloading {url}: {e}")
        #     return None
        return f"{self.storage_path}/{filename or url.split('/')[-1]}" # Placeholder

    def process_image(self, image_path: str, target_size: Optional[Tuple[int, int]] = None) -> Optional[str]:
        '''Processes an image (e.g., resize, convert format).

        Args:
            image_path: Path to the local image file.
            target_size: Optional tuple (width, height) to resize the image to.

        Returns:
            Path to the processed image, or None if processing failed.
        '''
        # Placeholder for image processing logic (e.g., using Pillow)
        print(f"Processing image {image_path}...")
        # Example:
        # from PIL import Image
        # try:
        #     img = Image.open(image_path)
        #     if target_size:
        #         img = img.resize(target_size)
        #     # Save processed image, potentially with a new name
        #     # return processed_image_path
        # except Exception as e:
        #     print(f"Error processing {image_path}: {e}")
        #     return None
        return image_path # Placeholder

if __name__ == '__main__':
    # Example Usage
    handler = ImageHandler()
    img_url = "http://example.com/image.jpg" # Replace with actual image URL
    downloaded_path = handler.download_image(img_url, "example.jpg")
    if downloaded_path:
        processed_path = handler.process_image(downloaded_path, target_size=(100, 100))
        if processed_path:
            print(f"Processed image saved at: {processed_path}") 