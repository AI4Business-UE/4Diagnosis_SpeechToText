/// <reference types="audioworklet" />

class BaseProcessor extends AudioWorkletProcessor {
    private inputSampleRate: number;
    private outputSampleRate: number;
    private taps: number;
    private numPhases: number;
    private ratio: number;
    private historySize: number;
    private filterCenter: number;
    private filterBank: Array<Float32Array>;
    private historyBuffer: Float32Array;
    private inputPosition: number;

    constructor(options: AudioWorkletNodeOptions) {
        super();

        const requestedOutputRate = options?.processorOptions?.outputSampleRate;
        this.inputSampleRate = sampleRate;
        this.outputSampleRate = Number.isFinite(requestedOutputRate) && requestedOutputRate > 0
            ? requestedOutputRate
            : sampleRate;

        this.taps = 33;
        this.numPhases = 1024;
        this.ratio = this.inputSampleRate / this.outputSampleRate;
        this.historySize = this.taps - 1;
        this.filterCenter = Math.floor(this.taps / 2);

        this.filterBank = this.createFilterBank();
        this.historyBuffer = new Float32Array(this.historySize);

        this.inputPosition = 0;
    }

    createFilterBank() {
        const filterBank = new Array(this.numPhases);
        const cutoff = 0.5 * Math.min(1, this.outputSampleRate / this.inputSampleRate) * 0.94;

        for (let phase = 0; phase < this.numPhases; phase++) {
            const fraction = phase / this.numPhases;
            const coefficients = new Float32Array(this.taps);

            let coefficientSum = 0;
            for (let tap = 0; tap < this.taps; tap++) {
                const offset = tap - this.filterCenter - fraction;
                const sincArgument = 2 * cutoff * offset;
                const sincValue = sincArgument === 0 ? 1 : Math.sin(Math.PI * sincArgument) / (Math.PI * sincArgument);

                const window = 0.5 * (1 - Math.cos((2 * Math.PI * tap) / (this.taps - 1)));
                const coefficient = 2 * cutoff * sincValue * window;

                coefficients[tap] = coefficient;
                coefficientSum += coefficient;
            }

            if (coefficientSum !== 0) {
                for (let tap = 0; tap < this.taps; tap++) {
                    coefficients[tap] /= coefficientSum;
                }
            }

            filterBank[phase] = coefficients;
        }

        return filterBank;
    }

    process(inputs: Float32Array[][], outputs: Float32Array[][]) {
        const outputChannel = outputs[0]?.[0];
        if (outputChannel) {
            outputChannel.fill(0);
        }

        const inputChannel = inputs[0]?.[0];
        if (!inputChannel || inputChannel.length === 0) {
            return true;
        }
        const workingBuffer = new Float32Array(this.historySize + inputChannel.length);
        workingBuffer.set(this.historyBuffer, 0);
        workingBuffer.set(inputChannel, this.historySize);

        const outputCapacity = Math.ceil(inputChannel.length / this.ratio) + 2;
        const resampledOutput = new Float32Array(outputCapacity);
        let outputIndex = 0;
        
        while (outputIndex < resampledOutput.length) {
            const integerPosition = Math.floor(this.inputPosition);
            const fraction = this.inputPosition - integerPosition;

            let phaseIndex = Math.round(fraction * this.numPhases);
            let samplesPosition = integerPosition;

            if (phaseIndex === this.numPhases) {
                phaseIndex = 0;
                samplesPosition += 1;
            }

            const startIndex = this.historySize + samplesPosition - this.filterCenter;
            if (startIndex < 0 || startIndex + this.taps > workingBuffer.length) {
                break;
            }

            const filter = this.filterBank[phaseIndex];
            let sampleSum = 0;

            for (let tap = 0; tap < this.taps; tap++) {
                sampleSum += workingBuffer[startIndex + tap] * filter[tap];
            }

            resampledOutput[outputIndex] = sampleSum;
            outputIndex += 1;
            this.inputPosition += this.ratio;
        }

        this.historyBuffer = workingBuffer.slice(
            -this.historySize
        );
        this.inputPosition -= inputChannel.length;

        const output = resampledOutput.slice(0, outputIndex);

        if (output.length > 0) {
            this.port.postMessage(output, [output.buffer]);
        }

        return true; 
    }
}

registerProcessor('base-processor', BaseProcessor);