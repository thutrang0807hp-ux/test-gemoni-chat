import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from browser_bridge import GeminiWorkspace, WorkspaceError
from PIL import Image


def png(color):
    output = io.BytesIO()
    Image.new('RGB', (8, 8), color).save(output, format='PNG')
    return output.getvalue()


class ReferenceBridgeTest(unittest.TestCase):
    def test_optional_references_snapshot_order_and_prompt(self):
        with TemporaryDirectory() as folder:
            workspace = GeminiWorkspace(Path(folder))
            workspace.start = lambda: None
            paths = [Path(folder) / 'gốc.png', Path(folder) / 'sản phẩm.png']
            expected = [png('red'), png('blue')]
            for path, data in zip(paths, expected):
                path.write_bytes(data)
            calls = []
            def request(action, **values):
                calls.append(values)
                self.assertEqual(action, 'image')
                self.assertEqual(values['prompt'], 'V6 ' + 'x' * 13000)
                if 'references' in values:
                    self.assertEqual([Path(p).read_bytes() for p in values['references']], expected)
                    self.assertTrue(all(Path(p).parent == Path(values['output']).parent for p in values['references']))
                Path(values['output']).write_bytes(png('green'))
                return {'saved': True}
            workspace.request = request
            for refs in [(), paths, paths]:
                result = workspace.create_image('V6 ' + 'x' * 13000, refs)
                self.assertEqual(Image.open(io.BytesIO(result)).getpixel((0, 0)), (0, 128, 0))
            self.assertNotIn('references', calls[0])
            self.assertTrue(all(not Path(p).exists() for p in calls[-1]['references']))

    def test_invalid_image_never_submitted(self):
        with TemporaryDirectory() as folder:
            workspace = GeminiWorkspace(Path(folder))
            workspace.start = lambda: None
            workspace.request = lambda *args, **kwargs: self.fail('Invalid image submitted')
            path = Path(folder) / 'bad.png'
            path.write_bytes(b'not an image')
            with self.assertRaises(OSError):
                workspace.create_image('prompt', [path])


if __name__ == '__main__':
    unittest.main()
