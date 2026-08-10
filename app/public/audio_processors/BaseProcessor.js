class BaseProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
        const firstChannelData = inputs[0];
        if (firstChannelData.length > 0) {
            this.port.postMessage(firstChannelData);
        }
        return true; 
    }
}

registerProcessor('base-processor', BaseProcessor);