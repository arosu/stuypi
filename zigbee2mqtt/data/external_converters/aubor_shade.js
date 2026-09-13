const fz = require('zigbee-herdsman-converters/converters/fromZigbee');
const tz = require('zigbee-herdsman-converters/converters/toZigbee');
const exposes = require('zigbee-herdsman-converters/lib/exposes');
const reporting = require('zigbee-herdsman-converters/lib/reporting');

const e = exposes.presets;

const invertedPositionIeee = new Set([
    '0x10a562fffe557c70',
]);

function deviceIeeeFromEntity(entity) {
    return entity.deviceIeeeAddress || entity.device?.ieeeAddr;
}

function hasInvertedPosition(ieee) {
    return invertedPositionIeee.has(String(ieee).toLowerCase());
}

function stateFromPosition(position) {
    if (position === 100) return 'OPEN';
    if (position === 0) return 'CLOSE';
}

const auborBattery = {
    cluster: 'genPowerCfg',
    type: ['attributeReport', 'readResponse'],
    convert: (model, msg) => {
        if (Object.prototype.hasOwnProperty.call(msg.data, 'batteryPercentageRemaining')) {
            return {battery: Math.min(msg.data.batteryPercentageRemaining * 2, 100)};
        }
    },
};

const auborCoverPosition = {
    ...fz.cover_position_tilt,
    convert: (model, msg, publish, options, meta) => {
        const result = fz.cover_position_tilt.convert(model, msg, publish, options, meta);
        if (hasInvertedPosition(msg.device.ieeeAddr) && typeof result?.position === 'number') {
            result.position = 100 - result.position;
        }
        if (typeof result?.position === 'number') {
            const state = stateFromPosition(result.position);
            if (state) result.state = state;
        }
        return result;
    },
};

const auborCoverPositionSet = {
    ...tz.cover_position_tilt,
    convertSet: async (entity, key, value, meta) => {
        const requestedValue = key === 'position' && hasInvertedPosition(deviceIeeeFromEntity(entity)) && typeof value === 'number'
            ? 100 - value
            : value;
        const result = await tz.cover_position_tilt.convertSet(entity, key, requestedValue, meta);
        if (key === 'position' && requestedValue !== value && result?.state?.position !== undefined) {
            result.state.position = value;
        }
        return result;
    },
};

module.exports = {
    zigbeeModel: ['TLSR82xx'],
    fingerprint: [
        {modelID: 'TLSR82xx', manufacturerName: 'Aubor'},
    ],
    model: 'Allesin_Roller_Shade',
    vendor: 'Allesin',
    description: 'Zigbee roller shade',
    fromZigbee: [
        auborCoverPosition,
        auborBattery,
    ],
    toZigbee: [
        tz.cover_state,
        auborCoverPositionSet,
    ],
    exposes: [
        e.cover_position(),
        e.battery(),
    ],
    configure: async (device, coordinatorEndpoint) => {
        const endpoint = device.getEndpoint(1);
        await reporting.bind(endpoint, coordinatorEndpoint, ['closuresWindowCovering', 'genPowerCfg']);
        await reporting.currentPositionLiftPercentage(endpoint);
        await reporting.batteryPercentageRemaining(endpoint);
    },
};
