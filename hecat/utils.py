"""hecat - common utilities"""
import os

def list_files(directory):
    """list files in a directory, return an alphabetically sorted list"""
    source_files = []
    for _, _, files in os.walk(directory):
        for file in files:
            source_files.append(file)
    return source_files

def to_kebab_case(string):
    """convert a string to kebab-case, remove some special characters"""
    replacements = {
        ' ': '-',
        '(': '',
        ')': '',
        '&': '',
        '/': '',
        ',': ''
    }
    newstring = string.translate(str.maketrans(replacements)).lower()
    return newstring
