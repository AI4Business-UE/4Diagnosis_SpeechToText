
# Kolo naukowe AI4Business, Uniwersytet Ekonomiczny we Wrocławiu 2025

from pydub import AudioSegment
from typing import List
from logging import info, warning
from copy import deepcopy


# created to pass references in __chunks and __chunks_list in AudioChunkParser object instead of holding the objects
# this solution is more memory efficient and allows more control over the data and removes redundancies


class AudioChunk(object):
    """
    Chunk class objects contain sliced audio objects

    Attributes:
        __ID                        : int, private, Unique chunk ID
        __offset                    : int, private, Timestamp indicating beginning of the chunk
        __audio                     : AudioSegment, private, The sound chunk object itself
        __path_to_audio             : str, private, Path of the location of the audio segment file
        __is_processed              : bool, private, Boolean value indicating whether the chunk has been fed to the STT model
        __predicted_text            : str, private, Inferred text based on the STT prediction
        __previous_predictions      : List[str], private, List storing all previous predictions
        __length                    : int, private, Lenght of the chunk in milliseconds
    """

    # private class fields

    __ID : int
    __offset : int
    __audio : AudioSegment
    __path_to_audio : str
    __is_processed : bool
    __predicted_text : str
    __previous_predictions : List[str]    # added in case an analysis was needed on improvements in predictions after changes


    def __init__(
        self,
        ID: int,
        offset: int,
        audio: AudioSegment = None,
        path_to_audio: str = "",
        predicted_text: str = ""
    ):
        self.__ID = ID
        self.__offset = offset
        self.__audio = audio
        self.__path_to_audio = path_to_audio
        self.__is_processed = bool(predicted_text)
        self.__predicted_text = predicted_text
        self.__previous_predictions = []
        self.__length = len(self.__audio) if self.__audio else 0
        info("Initialized audio chunk:\n" + str(self))


    # getters

    @property
    def ID(self) -> int:
        return self.__ID

    @property
    def offset(self) -> int:
        return self.__offset

    def get_audio(self) -> AudioSegment:
        return deepcopy(self.__audio)       # ensured that copy is passed and the original object is not modified undeliberately

    @property
    def path_to_audio(self) -> str:
        return self.__path_to_audio

    @property
    def is_processed(self):
        return self.__is_processed

    @property
    def predicted_text(self) -> str:
        return self.__predicted_text

    @property
    def previous_predictions(self) -> List[str]:
        return self.__previous_predictions

    @property
    def length(self) -> int:
        return self.__length

    # setters and modifiers

    def set_ID(self, new_ID : int, force: bool = False) -> None:
        """ Method for setting new ID for an existing Chunk \n
        Warning! IDs are unique for every AudioChunk object. \n
        \t Changing ID for a Chunk is highly unadviced unless  """
        if not force:
            warning(f"Changing ID of Chunk {self.ID} to {new_ID}. Use force=True to suppress this warning.")
        self.__ID = new_ID

    def set_offset(self, new_offset : int) -> None:
        self.__offset = new_offset

    def update_audio(self, new_audio : AudioSegment) -> bool:
        """ Method allowing to set or swap the audio recording object of the Chunk. """
        if self.__audio is None:
            self.__audio = new_audio
        elif self.__audio != new_audio:
            self.__audio = new_audio
        else:
            warning(f"Chunk {self.__ID}: New audio identical to existing audio. No update performed.")
            return False
        return True

    @is_processed.setter
    def is_processed(self, new_state : bool) -> None:
        if self.__is_processed != new_state:
            self.__is_processed = new_state
            info(f"Chunk {self.ID}: is_processed property set to {new_state}")
        else:
            info(f"Chunk {self.ID}: is_processed property ({self.is_processed}) unchanged.")

    @predicted_text.setter
    def predicted_text(self, text: str) -> None:
        """ Setter: Property modifier that ensures all inferred texts are to be recorded. """
        if self.__predicted_text != "":
            self.__previous_predictions.append(self.__predicted_text)
        self.__predicted_text = text
        self.__is_processed = text != ""
        info(f"Chunk {self.ID}: Predicted text set to '{text}'" if text else f"Chunk {self.ID}: Predicted text cleared.")



    # comparison operators - will come in handy for sorting chunks in Lists or if iterator is implemented

    def __eq__(self, other : "AudioChunk"):
        return self.ID == other.ID

    def is_same(self, other : "AudioChunk") -> bool:
        """ Method to check if there are any differences between two AudioChunk objects. """
        return (self.ID == other.ID and
                self.offset == other.offset and
                self.is_processed == other.is_processed and
                self.predicted_text == other.predicted_text and
                self.path_to_audio == other.path_to_audio and
                self.get_audio() == other.get_audio())

    def __ne__(self, other : "AudioChunk"):
        return self.ID != other.ID

    def __gt__(self,other : "AudioChunk"):
        return self.ID > other.ID

    def __ge__(self, other : "AudioChunk"):
        return self.ID >= other.ID

    def __lt__(self,other : "AudioChunk"):
        return self.ID < other.ID

    def __le__(self, other : "AudioChunk"):
        return self.ID <= other.ID


    # overloading str(Chunk) - can be helpful to analyze the chunks e.g. if printed as list

    def __str__(self) -> str:
        temp_str = f'Chunk ID: {self.ID}, offset: {self.offset}, {"Passed for processing" if self.is_processed else "Not passed for processing yet"}, '
        temp_str += f'Predicted text: "{self.__predicted_text}"' if self.__predicted_text else 'No text predicted'

        return temp_str
