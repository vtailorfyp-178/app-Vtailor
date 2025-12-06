def validate_image(file):
    """
    Validates the uploaded image file.

    Parameters:
    - file: The image file to validate.

    Returns:
    - bool: True if the image is valid, False otherwise.
    - str: A message indicating the result of the validation.
    """
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    max_file_size = 5 * 1024 * 1024  # 5 MB

    if not file:
        return False, "No file uploaded."

    if file.size > max_file_size:
        return False, "File size exceeds the maximum limit of 5 MB."

    extension = file.filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        return False, f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}."

    return True, "Image is valid."