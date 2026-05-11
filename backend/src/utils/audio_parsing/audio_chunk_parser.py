
# Kolo naukowe AI4Business, Uniwersytet Ekonomiczny we Wrocławiu 2025

from typing import List, Tuple, Dict
from logging import info, warning

from pydub import AudioSegment, silence
from audio_chunk import AudioChunk


class AudioChunkParser:
    """
    General class for parsing audio file info discrete chunks using silence detection and offset logic.\n
    Provides utilities for Audio Chunk tracking and STT preprocessing.
    """

    __OFFSETS : List[ Tuple[int, int] ] # Tuple (ID of the offset, Timestamp in milliseconds)
    __CHUNKS : List[ AudioChunk ]
    __CHUNKS_MAP : Dict[ int, AudioChunk ]


    # public constructor - TODO examine whether to use the Singleton Design Pattern for this class
    def __init__(self):

        # defining empty private fields
        self.__OFFSETS = []
        self.__CHUNKS = []
        self.__CHUNKS_MAP = {}


    # getter provides a copy and ensures that the main offsets list is not undeliberately modified
    def get_offsets(self) -> List[Tuple[int, int]]:
        temp_offsets_list = [ (index, timestamp) for (index, timestamp) in enumerate(self.__OFFSETS) ]
        return temp_offsets_list


    def detect_silence_offsets(self, audio: AudioSegment, min_silence_len: int = 50, silence_thresh: int = -50) -> List[Tuple[int, int]]:
        """
        Detects silence in an audio segment with adjustable sensitivity.

        Args:
            audio (AudioSegment): The audio to analyze.
            min_silence_len (int): Minimum length of silence in ms. Default is 500ms.
            silence_thresh (int): Silence threshold in dBFS. Default is -40dBFS.
                                    A more sensitive threshold will detect quieter sounds as silences.

        Returns:
            List[Tuple[int, int]]: List of tuples (start_ms, end_ms) where silence was detected.
        """
        silence_ranges = silence.detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)

        info(f"Detected {len(silence_ranges)} silent sections.")

        return silence_ranges


    # method into the internal self.__offsets to load the offset from the external
    # source like a function or a yield from a model that determines the timestamps of the pauses and words
    def load_offsets(self, new_offsets : List[Tuple[int,int]]) -> bool:

        # here it might be needed to write an ensurement check if the current_offsets
        # contains only new and unique offsets - if it doesn't, it will be needed to check
        # for the new offsets only before adding them to the main list
        try:
            for (index, timestamp) in enumerate(new_offsets):
                self.__OFFSETS.append((index, timestamp))
        #catching in case of deadlock
        except RuntimeError as re:
            info(re)
            return False

        return True


    def get_chunk(self, id :int) -> AudioChunk:
        # here im not sure if i should return the reference to the object of the copy
        return self.__CHUNKS_MAP[id]        # returning the reference for now TODO check if viable later


    def get_chunks(self) -> List[AudioChunk]:
        return self.__CHUNKS.copy()  # Return shallow copy to prevent external modification


    def get_chunks_by_id(self, chunk_ids : List[int]) -> List[AudioChunk]:
        return sorted([self.__CHUNKS_MAP[id] for id in chunk_ids])      # returning the references for now TODO check if viable later


    def get_last_n_chunks(self, n : int) -> List[AudioChunk]:
        if n > len(self.__CHUNKS):
            n = len(self.__CHUNKS)
        return self.__CHUNKS[-n:]


    def remove_chunk(self, chunk : AudioChunk) -> bool:
        """ Method for removing AudioChunk object and it's appearances from
            the AudioChunkParser's List and Map by using a reference to
            the AudioChunk object. """
        id = chunk.ID
        if id in self.__CHUNKS_MAP.keys():
            self.__CHUNKS.remove(chunk)
            del chunk
            del self.__CHUNKS_MAP[id]
            info(f"Chunk {id} has been removed successfully.")
            return True
        else:
            warning(f"Chunk {id} not found.")
            return False


    def remove_chunk_by_id(self, id : int) -> bool:
        """ Method for removing AudioChunk object and it's appearances from
            the AudioChunkParser's List and Map by using chunk's id. """
        if id in self.__CHUNKS_MAP.keys():
            for chunk in self.__CHUNKS:
                if chunk.ID == id:
                    self.__CHUNKS.remove(chunk)
                    del chunk
            del self.__CHUNKS_MAP[id]
            info(f"Chunk {id} has been removed successfully.")
            return True
        else:
            warning(f"Chunk {id} not found.")
            return False


    def remove_chunks(self, chunks : List[AudioChunk]) -> bool:

        for chunk in chunks:
            if not self.remove_chunk(chunk):
                warning(f"Removal of chunks {[c.ID for c in chunks]} have failed. Chunk {chunk.ID} not found.")
                return False

        info(f"Chunks of IDs {[c.ID for c in chunks]} removed successfully.")
        return True


    def remove_last_n_chunks(self, n : int) -> bool:
        """
        Method for removing last N chunks whereas N is an integer.\n
        Method will come in handy when e.g. end-user would want to remove last N chunks.
        """
        return self.remove_chunks(self.get_last_n_chunks(n))


    def remove_last_n_words(self, n : int) -> bool:
        """
        Method for removing last N words whereas N is an integer.\n
        Method will come in handy when e.g. end-user would want to remove last N words.\n
        Current implementation rounds-up the removal of chunks - e.g. if given chunk accounts for
        two separate predicted words and the provided number of words expects only one of them to
        be removed, the other one will also be deleted as the chunk containing them will not be divided.
        """
        words_accounted_for = 0

        for i, chunk in enumerate(reversed(self.__CHUNKS), start=1):

            if chunk.is_processed and len(chunk.predicted_text) != 0:
                words_accounted_for += len(chunk.predicted_text.split(sep=" "))     # for now the separator between words is a single space character

            if words_accounted_for >= n:
                self.remove_last_n_chunks(i)
                info(f"Last {words_accounted_for} words has been deleted and last {i} chunks has been removed.")
                return True

        info("No words nor chunks has been removed")
        return False


    def remove_last_n_seconds(self, n : float) -> bool:
        """
        Method for removing last N seconds whereas N is an float.\n
        Method will come in handy when e.g. end-user would want to remove last N seconds of recording.\n
        Current implementation rounds-up the removal of chunks - e.g. if given chunk accounts for
        2.5 seconds and the provided amount of time expects only for example 2 seconds to be removed,
        the reminder of 0.5 seconds will also be deleted as the chunk containing the audio will not be divided.
        """

        milliseconds_accounted_for = 0

        for i, chunk in enumerate(reversed(self.__CHUNKS), start=1):

            milliseconds_accounted_for += chunk.length

            if milliseconds_accounted_for/1000 >= n:
                self.remove_last_n_chunks(i)
                info(f"Last {milliseconds_accounted_for/1000} words has been deleted and last {i} chunks has been removed.")
                return True

        info("No chunks has been removed")
        return False


    def update_last_n_chunks(self, n: int, chunks : List[AudioChunk]) -> bool:
        """
        Method for updating last N chunks whereas N is an integer.\n
        A list with new or changed chunks must be provided as an argument.
        """
        if len(chunks) != n:
            warning(f"Expected {n} chunks, received {len(chunks)}.")
            return False
        # self.remove_last_n_chunks(n)      # TODO not sure if removing them is viable since updating can also mean updating the predicted text, come back to it later
        return self.update_chunks(chunks)


    def is_chunk_already_in_chunks(self, chunk_or_id: int | AudioChunk) -> bool:
        """
        Method checking based on Chunk's ID whether given chunk is already accounted for within the __CHUNKS and __CHUNKS_MAP.\n
        This method does NOT check if the given chunks are identical or checks the differences
        """
        if isinstance(chunk_or_id, AudioChunk):
            return chunk_or_id.ID in self.__CHUNKS_MAP
        elif isinstance(chunk_or_id, int):
            return chunk_or_id in self.__CHUNKS_MAP
        else:
            raise TypeError("Expected an int or AudioChunk instance")


    def __is_existing_chunk_the_same(self, chunk : AudioChunk) -> bool:
        """
        Private method for checking whether the given chunk is the same as the one with the same ID found in the __CHUNKS and __CHUNKS_MAP.\n
        Important: This method assumes the chunk with given ID already exists.
        """
        existing_chunk = self.__CHUNKS_MAP.get(chunk.ID)
        return chunk.is_same(existing_chunk)


    def update_chunks(self, chunks : List[AudioChunk]) -> bool:
        """
        Method for updating AudioChunks data structure by either adding a newly sliced chunks
        or updating already existing ones.
        """
        for chunk in chunks:

            if self.is_chunk_already_in_chunks(chunk.ID):

                if self.__is_existing_chunk_the_same(chunk):
                    info(f"Chunk {chunk.ID} not updated in __chunks since no changes recognised.")

                else:
                    self.__CHUNKS_MAP[chunk.ID] = chunk
                    for i, c in enumerate(self.__CHUNKS):
                        if c.ID == chunk.ID:
                            self.__CHUNKS[i] = chunk
                            break

            else:
                # behaviour if new chunk added
                self.__CHUNKS.append(chunk)
                self.__CHUNKS_MAP[chunk.ID] = chunk

        return True                                                                             #TODO add boiler plating for return


    def load_sound(self, path_to_audio : str) -> AudioSegment:
        """
        Method for loading the sound from file in provided path.

        Raises
        ------
        ValueError
        """
        if len(path_to_audio) == 0:
            raise(ValueError("An empty path_to_audio string provided"))
        else:
            wave = AudioSegment.from_file(path_to_audio, format="wav")
            return wave


    def cut_sound_into_chunks(self, wave : AudioSegment) -> bool:
        """
        Method that slices the AudioSegment object into chunks based on the offsets registered.
        """
        offsets = self.get_offsets()

        if len(offsets) < 2:
            warning("Not enough offsets to form chunks.")
            return False

        temp_chunks = []
        for i, (id, start_offset) in enumerate(offsets[:-1]):
            end_offset = offsets[i+1][1]
            slice = wave[start_offset:end_offset]
            new_chunk = AudioChunk(ID=id, offset=start_offset, audio=slice)
            temp_chunks.append(new_chunk)

        if self.update_chunks(temp_chunks):
            info("Audio sliced successfully")
            return True

        warning("Audio slicing usuccessful")
        return False


    def chunk_em_up(self, path_to_audio : str) -> bool:
        """
        Method for slicing the audio file at the given path into AudioChunks based on the detected silences in speech.
        """
        wave = self.load_sound(path_to_audio)
        silences = self.detect_silence_offsets(wave)
        self.load_offsets( [(i, s[0]) for i, s in enumerate(silences)] + [(len(silences), len(wave))] )
        return self.cut_sound_into_chunks(wave)


