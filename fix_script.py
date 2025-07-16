#!/usr/bin/env python3
"""
Verify Plugin Fix Script
Run this to test if the plugin loading is working
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test if we can import the plugin files"""
    print("🧪 Testing plugin imports...")
    
    try:
        # Add current directory to path
        sys.path.insert(0, str(Path.cwd()))
        
        # Test importing plugin_base
        from plugins.plugin_base import PluginBase
        print("✅ plugin_base imported successfully")
        
        # Test importing relay_controller
        sys.path.append(str(Path("plugins/relay_controller")))
        from plugins.relay_controller.plugin import Plugin as RelayPlugin
        print("✅ relay_controller plugin imported successfully")
        
        # Test importing hello_world
        sys.path.append(str(Path("plugins/hello_world")))
        from plugins.hello_world.plugin import Plugin as HelloPlugin
        print("✅ hello_world plugin imported successfully")
        
        # Test creating instances
        plugin_dir = Path("plugins/relay_controller")
        relay_instance = RelayPlugin(plugin_dir)
        print(f"✅ relay_controller instance created: {relay_instance.name}")
        
        plugin_dir = Path("plugins/hello_world") 
        hello_instance = HelloPlugin(plugin_dir)
        print(f"✅ hello_world instance created: {hello_instance.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_plugin_manager():
    """Test the plugin manager"""
    print("\n🧪 Testing plugin manager...")
    
    try:
        from config_manager import ConfigManager
        from plugin_manager import PluginManager
        
        # Create managers
        config_manager = ConfigManager()
        plugin_manager = PluginManager(config_manager=config_manager)
        
        print("✅ Managers created successfully")
        
        # Discover plugins
        discovered = plugin_manager.discover_plugins()
        print(f"✅ Discovered plugins: {discovered}")
        
        # Try to load plugins
        for plugin_name in discovered:
            success = plugin_manager.load_plugin(plugin_name)
            print(f"{'✅' if success else '❌'} Load {plugin_name}: {success}")
            
            if success:
                enable_success = plugin_manager.enable_plugin(plugin_name)
                print(f"{'✅' if enable_success else '❌'} Enable {plugin_name}: {enable_success}")
        
        # Show loaded plugins
        loaded = list(plugin_manager.loaded_plugins.keys())
        print(f"✅ Loaded plugins: {loaded}")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🚀 Plugin Fix Verification")
    print("=" * 30)
    
    # Test imports
    import_success = test_imports()
    
    # Test plugin manager
    manager_success = test_plugin_manager()
    
    print("\n📊 Results:")
    print(f"Import Test: {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"Manager Test: {'✅ PASS' if manager_success else '❌ FAIL'}")
    
    if import_success and manager_success:
        print("\n🎉 All tests passed! Your plugins should work now.")
        print("Run your main app with: python3 app.py")
    else:
        print("\n⚠️ Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()