from collections import defaultdict

class EventSystem:
    #reliable event management with direct callbacks
    def __init__(self):
        #event_type -> list of callback functions
        self.subscribers = defaultdict(list)
        
        #component_name -> list of (callback, event_types)
        self.component_subscribers = defaultdict(list)
    
    #register callback for specific event types
    def subscribe(self, event_types, callback):
        if isinstance(event_types, str):
            event_types = [event_types]
        
        for event_type in event_types:
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)
    
    #register callback for specific component events
    def subscribe_component(self, component_name, event_types, callback):
        if isinstance(event_types, str):
            event_types = [event_types]
        
        #store callback with component filter
        self.component_subscribers[component_name].append((callback, event_types))
        
        #also add to main subscribers for delivery
        for event_type in event_types:
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)
    
    #publish event to all relevant subscribers
    def publish(self, event_type, *args, **kwargs):
        if event_type not in self.subscribers:
            return
        
        #extract component context from event args
        component_name = kwargs.get('component_name')
        if not component_name and args:
            if isinstance(args[0], str):
                component_name = args[0]
        
        #deliver to all subscribers
        dead_callbacks = []
        
        for callback in self.subscribers[event_type]:
            try:
                #check if this callback needs component filtering
                should_deliver = True
                
                if component_name:
                    #check if callback is component-specific
                    is_component_specific = False
                    for comp_name, callback_list in self.component_subscribers.items():
                        for stored_callback, event_types in callback_list:
                            if stored_callback == callback and event_type in event_types:
                                if comp_name != component_name:
                                    should_deliver = False
                                is_component_specific = True
                                break
                        if is_component_specific:
                            break
                
                if should_deliver:
                    callback(event_type, *args, **kwargs)
                    
            except Exception as e:
                #remove failed callbacks
                dead_callbacks.append(callback)
        
        #clean up dead callbacks
        for dead_callback in dead_callbacks:
            self.unsubscribe(dead_callback)
    
    #unsubscribe callback from all events
    def unsubscribe(self, callback):
        #remove from main subscribers
        for event_type in list(self.subscribers.keys()):
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
            
            #clean up empty lists
            if not self.subscribers[event_type]:
                del self.subscribers[event_type]
        
        #remove from component subscribers
        for component_name in list(self.component_subscribers.keys()):
            self.component_subscribers[component_name] = [
                (cb, events) for cb, events in self.component_subscribers[component_name]
                if cb != callback
            ]
            
            #clean up empty lists
            if not self.component_subscribers[component_name]:
                del self.component_subscribers[component_name]
    
    #get subscriber count for debugging
    def get_stats(self):
        total_subscribers = 0
        event_counts = {}
        
        for event_type, subscribers in self.subscribers.items():
            event_counts[event_type] = len(subscribers)
            total_subscribers += len(subscribers)
        
        return {
            'total_subscribers': total_subscribers,
            'event_counts': event_counts
        }
    
    #force cleanup of all subscribers
    def cleanup(self):
        self.subscribers.clear()
        self.component_subscribers.clear()

#global event system instance
_event_system = EventSystem()

#convenient functions for external use
def subscribe(event_types, callback):
    _event_system.subscribe(event_types, callback)

def subscribe_component(component_name, event_types, callback):
    _event_system.subscribe_component(component_name, event_types, callback)

def publish(event_type, *args, **kwargs):
    _event_system.publish(event_type, *args, **kwargs)

def unsubscribe(callback):
    _event_system.unsubscribe(callback)

def cleanup():
    _event_system.cleanup()

def get_stats():
    return _event_system.get_stats()

#event type constants for consistency
class Events:
    #component-specific events
    COMPONENT_POSITION_CHANGED = "component_position_changed"
    COMPONENT_RANGE_CHANGED = "component_range_changed"
    COMPONENT_SETTING_CHANGED = "component_setting_changed"
    COMPONENT_INDEX_SWAPPED = "component_index_swapped"
    
    #system events
    CONNECTION_CHANGED = "connection_changed"
    ALL_SERVOS_RESET = "all_servos_reset"
    
    #sequence events
    SEQUENCE_KEYFRAME_ADDED = "sequence_keyframe_added"
    SEQUENCE_KEYFRAME_REMOVED = "sequence_keyframe_removed"
    SEQUENCE_UPDATED = "sequence_updated"
    SEQUENCE_LOADED = "sequence_loaded"
    SEQUENCE_CLEARED = "sequence_cleared"
    
    #playback events
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYBACK_ERROR = "playback_error"